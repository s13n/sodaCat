"""Derive concise enum value names from their descriptions.

NXP SVDs auto-generate enum value names by uppercasing the description and
truncating at 20 characters.  The result is ugly (`ENABLE_CAN_INTERRUPT`,
`DISABLE_CAN_INTERRUP`) and prone to within-field name clashes (two distinct
descriptions collapsing to the same 20-char prefix).  Since the field's own
description usually carries the context ("Module interrupt enable"), the
value-level names need only encode the discriminating part — `ENABLE` and
`DISABLE` are entirely adequate.

The simplifier produces a candidate name from each description in two stages:

  1. **Boolean lead/trail match** — descriptions starting or ending with words
     like "Enable", "Disabled", "Set", "Cleared", "Active", "Inactive",
     "Unchanged" map to canonical short names.  Catches the majority of
     2-state fields.

  2. **Leading content tokens** — first N content words of the description
     (stopwords filtered, camelCase / acronym / digit-letter boundaries
     split), uppercased, underscore-joined.  N grows from 2 upward until
     names are unique within the field, falling back to a `_<value>` suffix
     if no token count produces uniqueness.

The candidate replaces the original only when the original looks
truncated (ends with `_`, or exactly matches the mechanical mangling of
its description at any cut-off in 18..23 chars) or has a within-field
clash with a sibling.  Hand-written names — clean short ones like
`MSGTRANSFER`, `PASSIVE`, `BUSOFF` and longer ones like the MCXN
`NONSECURE_PRIV_USER_ALLOWED` — are kept as-is.
"""

import re

from svd import _yaml_safe_str

# Boolean lead-word patterns: first word of the description -> short name.
# Deliberately omitted: 'no', 'yes' — too terse on their own and tend to
# collide with content like "No error" / "No transmission" where a 2-token
# extract gives a more useful name.
_BOOL_LEAD = {
    'enable':   'ENABLE',
    'enables':  'ENABLE',
    'enabled':  'ENABLED',
    'disable':  'DISABLE',
    'disables': 'DISABLE',
    'disabled': 'DISABLED',
    'set':      'SET',
    'sets':     'SET',
    'clear':    'CLEAR',
    'clears':   'CLEAR',
    'cleared':  'CLEAR',
    'reset':    'RESET',
    'resets':   'RESET',
    'active':   'ACTIVE',
    'inactive': 'INACTIVE',
}

# Boolean trail-word patterns: last word of the first sentence -> short name.
# Only consulted when the lead word didn't match.
_BOOL_TRAIL = {
    'enabled':   'ENABLED',
    'disabled':  'DISABLED',
    'set':       'SET',
    'cleared':   'CLEAR',
    'active':    'ACTIVE',
    'inactive':  'INACTIVE',
    'unchanged': 'UNCHANGED',
}

# English stopwords skipped when extracting content tokens.  Kept short:
# only words that are almost never the discriminator between sibling enums.
# 'no' and 'not' are deliberately NOT included — they often carry the
# meaningful negation between two sibling enums.
_STOPWORDS = frozenset({
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'this', 'that', 'these', 'those', 'of', 'in', 'on', 'at', 'to', 'for',
    'with', 'by', 'from', 'as', 'and', 'or', 'but', 'will', 'has', 'have',
    'had', 'its', 'their', 'it', 'one', 'when', 'while', 'if', 'than',
})

# Word-boundary insertions applied before tokenization, in order:
#   * acronym-then-word: `CRCError` -> `CRC Error`
#   * camelCase:         `aB`       -> `a B`
#   * digit-then-upper:  `Bit1Error` (after camelCase) -> `Bit1 Error`
_BOUNDARY_PATTERNS = [
    re.compile(r'([A-Z])([A-Z][a-z])'),
    re.compile(r'([a-z])([A-Z])'),
    re.compile(r'(\d)([A-Z])'),
]
_TOKEN_SPLIT = re.compile(r'[^A-Za-z0-9]+')
_FIRST_SENTENCE = re.compile(r'^[^.!?]*')


def _first_sentence(text):
    if not text:
        return ''
    m = _FIRST_SENTENCE.match(text)
    return m.group(0) if m else text


def _tokenize(text):
    if not text:
        return []
    for pat in _BOUNDARY_PATTERNS:
        text = pat.sub(r'\1 \2', text)
    return [t.lower() for t in _TOKEN_SPLIT.split(text) if t]


def _content(tokens):
    """Drop stopwords and pure-digit tokens.

    Pure digits are dropped because they tend to be width markers ("29-bit
    extended" vs "11-bit standard") that survive tokenization but make
    poor identifier roots — `29_BIT` would sanitize to `V29_BIT` and lose
    the meaningful word ('extended'/'standard') that comes after.
    """
    return [t for t in tokens
            if t not in _STOPWORDS and not t.isdigit()]


def _join_n(tokens, n):
    if not tokens:
        return None
    return '_'.join(t.upper() for t in tokens[:n])


def _bool_match(tokens):
    if not tokens:
        return None
    lead = _BOOL_LEAD.get(tokens[0])
    if lead is not None:
        return lead
    trail = _BOOL_TRAIL.get(tokens[-1])
    if trail is not None:
        return trail
    return None


def _sanitize(name):
    """Ensure `name` is a valid C identifier.

    Token splitter restricts characters to [A-Za-z0-9_]; the only remaining
    risk is a leading digit, which we prefix with `V`.
    """
    if not name:
        return name
    if name[0].isdigit():
        return 'V' + name
    return name


_MANGLE = re.compile(r'[^A-Za-z0-9]+')


def _is_suspicious(name, description):
    """Whether the original SVD name shows mechanical-truncation evidence.

    NXP's MCUXpresso SVD generator derives enum names by mangling the
    description (non-alphanumeric runs to `_`, uppercase, stripped) and
    truncating at ~20 chars.  We classify a name as truncated when it
    exactly matches that mangling at any cut-off in 18..23, OR ends with
    `_` (the tell-tale trailing-underscore from a description that ended
    on punctuation right at the truncation boundary).

    This deliberately skips long-but-clean names like
    `NONSECURE_PRIV_USER_ALLOWED` (27 chars, hand-curated in MCX SVDs) —
    those don't match any truncation of their description and should be
    preserved as written.
    """
    if not name:
        return False
    if name.endswith('_'):
        return True
    if not description:
        return False
    mangled = _MANGLE.sub('_', description).upper().strip('_')
    for n in range(18, 24):
        if name == mangled[:n].rstrip('_'):
            return True
    return False


def derive_names(enums):
    """Compute one candidate short name per enum from its description.

    `enums` is a list of dicts with at least 'description'.  Returns a list
    of candidate names, parallel to `enums`.  Names are unique within the
    returned list (collisions resolved by appending `_<value>`).  Enums with
    no usable description map to None — callers should preserve the original
    name in that case.
    """
    n_enums = len(enums)
    candidates = [None] * n_enums
    sentence_tokens = [_tokenize(_first_sentence(e.get('description', '')))
                       for e in enums]

    # Stage 1: boolean lead/trail matches on the first sentence.
    for i, toks in enumerate(sentence_tokens):
        m = _bool_match(toks)
        if m is not None:
            candidates[i] = m

    # Stage 2: for unfilled slots, take leading content tokens of the full
    # description.  Increase token count until full set is unique.
    full_tokens = [_tokenize(e.get('description', '')) for e in enums]
    unfilled = [i for i, n in enumerate(candidates) if n is None
                and full_tokens[i]]
    if unfilled:
        for n in (2, 3, 4, 5):
            attempt = list(candidates)
            for i in unfilled:
                content = _content(full_tokens[i]) or full_tokens[i]
                attempt[i] = _join_n(content, n)
            assigned = [x for x in attempt if x is not None]
            if len(set(assigned)) == len(assigned):
                candidates = attempt
                break
        else:
            for i in unfilled:
                content = _content(full_tokens[i]) or full_tokens[i]
                candidates[i] = _join_n(content, 2)

    # Stage 3: dedup remaining clashes by appending the value.
    seen = {}
    for i, n in enumerate(candidates):
        if n is None:
            continue
        seen.setdefault(n, []).append(i)
    for name, idxs in seen.items():
        if len(idxs) > 1:
            for i in idxs:
                v = enums[i].get('value', i)
                candidates[i] = f"{name}_{v}"

    return [_sanitize(n) if n is not None else None for n in candidates]


def simplify_field_enums(field):
    """Replace enum names in a field with derived shorter names where helpful.

    Original names are preserved when they are clean (no truncation evidence,
    no within-field clash) and shorter than the candidate.  Operates in-place
    on `field['enumeratedValues']`.  Returns the count of names that changed.
    """
    enums = field.get('enumeratedValues') or []
    if not enums:
        return 0

    candidates = derive_names(enums)
    originals = [e.get('name') for e in enums]

    # If any sibling shares the same original name, every original in the
    # field is unsafe — fall back to the candidate (or a value-suffix).
    orig_counts = {}
    for n in originals:
        orig_counts[n] = orig_counts.get(n, 0) + 1
    field_has_clash = any(c > 1 for c in orig_counts.values())

    final = []
    for e, orig, cand in zip(enums, originals, candidates):
        if cand is None:
            final.append(orig)
            continue
        if field_has_clash:
            final.append(cand)
            continue
        if _is_suspicious(orig, e.get('description', '')):
            final.append(cand)
            continue
        # Original looks clean (no truncation evidence, no clash) — keep it
        # even if the candidate happens to be shorter.  Only mechanical
        # truncations are replaced; hand-written names are respected.
        final.append(orig)

    # Last-resort dedup: a kept original could now clash with a chosen
    # candidate at a different index (rare).  Append `_<value>` to break it.
    seen = {}
    for i, n in enumerate(final):
        seen.setdefault(n, []).append(i)
    for name, idxs in seen.items():
        if len(idxs) > 1:
            for i in idxs:
                v = enums[i].get('value', i)
                final[i] = f"{name}_{v}"

    changed = 0
    for e, new in zip(enums, final):
        if new and e.get('name') != new:
            # Quote YAML 1.1 bool literals (NO, ON, OFF, ...) so the name
            # survives a dump/load roundtrip as a string.
            e['name'] = _yaml_safe_str(new)
            changed += 1
    return changed


def _walk_fields(registers):
    """Yield every field dict reachable from a register list (incl. clusters)."""
    for r in registers or []:
        if not isinstance(r, dict):
            continue
        for f in r.get('fields') or []:
            yield f
        for inner in r.get('registers') or []:
            for f in inner.get('fields') or []:
                yield f


def simplify_block_enums(block_data):
    """Apply enum-name simplification across every field in the block.

    Returns the total number of enum names changed.
    """
    total = 0
    for fld in _walk_fields(block_data.get('registers') or []):
        total += simplify_field_enums(fld)
    return total
