# C header generation

The C header file generator is to be provided later. For now we just explain
some ramifications.

## C header style

When generating C headers, one is restricted by the limitations of the language.
Most prominently there is a lack of support for identifier scopes or namespaces,
which is generally addressed with name prefixes. The downside is that it leads
to long and verbose names.

C has the following distinct name spaces or scopes:

- The global (external) scope. Identifiers must be unique throughout all source
  files of a project, because they are visible by the linker.
- The file scope. Identifiers must be unique within the source file, including
  all headers it includes.
- The tag namespace. Identifiers must be unique within struct, union and enum
  tags.
- The block scope. Identifiers must be unique within a struct block or a code
  block, i.e. within a pair of curly braces.
- Preprocessor namespace. Identifiers must be unique at file scope.

A name declared at block scope hides the same name in outer scopes, including
file and global scopes. A tag name can be the same as a name at other scopes,
because it is always associated with the keywords `struct`, `union` or `enum`.
Names defined by the preprocessor hide all identical names defined elsewhere,
regardless of scope.

Avoiding preprocessor symbols as much as possible is desirable because of their
invasive nature and their lack of visibility for a debugger. This leaves the
struct/union/enum scopes for use by headers. Starting with C23 a fixed
underlying type can be given for an enum (supported in gcc >= 13).

Enum value names are in file scope and must be unique between different enums,
so prefixes will usually need to be used. Using the enum tag as the prefix is
the most straightforward solution.

### Reserved names

C mandates that valid identifier names begin with a letter or underscore,
followed by letters, underscores or digits in any mixture. Sticking to ASCII
characters is advisable, but since C99 Unicode escape sequences are also
supported within an identifier name. C23 rules that the first character must be
of Unicode class XID_Start, the remaining characters of class XID_Continue.
Lower and upper case characters are considered different.

There are the following exceptions:

- Language keywords may not be used as identifier names.
- Identifiers starting with two underscores are reserved.
- Identifiers starting with one underscore followed by an uppercase letter are
  reserved.
- Identifiers starting with one underscore and not followed by an uppercase
  letter may only be used at block scope.

Furthermore, other headers may define additional identifiers that populate the
global, file and/or tag namespaces. There's no fixed rule for those, so avoiding
a name clash is not always possible. Reducing the likelihood of such clashes
typically involves using name prefixes. It also helps to minimize the number of
headers that a source file includes.

Macro names are best restricted to use only uppercase letters to make them stand
out and reduce name clashes with other identifiers. We are trying to avoid them
altogether, however.
