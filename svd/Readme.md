# SVD file handling, and generation of database files from it

SVD files are provided for numerous ARM-based microcontrollers, either by
ARM/Keil or by the chip manufacturer. They contain a description of the
peripherals on the chip, and their registers, down to the level of individual
bits and bitfields. The main purpose of the file format is to support
information display in debuggers and other tools. The information, however, can
also be used to generate header files automatically that describe the
peripherals. Doing so can reduce the likelihood of errors in coding the headers,
and speed up coding of device drivers, since there is less manual work involved.

SVD (System View Description) is a file format based on XML, with its structure
defined here:

<http://www.keil.com/pack/doc/CMSIS/SVD/html/index.html>

<https://open-cmsis-pack.github.io/svd-spec/main/index.html>

Keil distributes SVD files as part of their processor support packs here:

<https://www.keil.com/dd2/pack/>

The pack files are actually ZIP files, even though they have a filename
extension of `.pack`. They can be opened with standard ZIP viewers.

Many other sources of SVD files exist, for example as a github repository:

<https://github.com/cmsis-svd/cmsis-svd-data>

## Critique of SVD files

SVD files are XML files accompanied by a Schema for validation. A single file
serves to describe an entire chip from the perspective of one processor core in
it. While this is convenient for debugger use, it has numerous drawbacks for
other uses, which make it desirable to come up with a different way of
organising the data. The chip manufacturers may elect to provide the data by
generating it from their internal design data, but until this happens, this
database here needs to be filled by scraping SVD files and some manual
massaging, using the tools provided here.

The drawbacks of using SVD files directly are numerous:

### Lack of genericity

The same function block (or "peripheral") might be used in a multitude of chips.
Its data is therefore replicated in numerous different SVD files. You don't
usually want to write drivers for each of the chips separately, you want to
exploit the fact that the function block is always the same. But which SVD file
do you base a generic driver on? You would also need to check if the different
versions in different SVDs are in fact identical, or if there are subtle but
important differences.

### Difficulty to extract commonality

The fact that several instances of the same function block are often described
separately in the SVD file does not only mean repetition of redundant
information, but also entails trivial differences between the instances. For
example, when two instances of an otherwise identical I2C controller are
included, there are not just two names for the instances, but often also
different names for registers or bitfields within registers, because the
instance number is contained in them. This is distinctly bad practice, since it
hinders writing a common driver, which relies on registers and bits having
common names.

This unfortunate situation extends to descriptions, which often are
instance-specific, too.

When generating a header file for a function block, this instance-specific
information would have to be rewritten to remove the instance specific detail,
and produce a file that only defines and describes the commonalities. This is
difficult to do automatically, as there are almost infinite variations how such
instance dependent information can appear in the data. Ultimately, at least part
of this is going to be manual work.

### No separation between SoC level and peripheral level

The chip manufacturers design the chips using function blocks from a library.
For example, a USART or an I2C controller are elements in an IP library (IP =
Intellectual Property), and the same function block can be used in multiple
instances on the same chip, or across different chips. In such a case the
register model and functionality is the same between all instances, but the
addresses, interrupt numbers, DMA requests, bus attachments, clock signals etc.
are going to be different for each instance.

When writing a driver for one of those function blocks, you want to mirror this
situation, i.e. you want to have common driver code for all instances, which
gets parameterized with the aspects that differ between the instances.

To facilitate that, you need an automatically generated header for the function
block, which omits all the information that is specific for an instance, like
the address or the interrupt number used. In the SVD file, there is often no
separation between common information and instance specific information. There
would be a mechanism for that, the `derivedFrom` attribute, but frequently this
is not used, but each instance repeats the common information along with the
specific data. This generates rather a lot of redundancy and inflates the file.

The information that is specific to the way the chip integrates the various
function blocks, i.e. addresses, interrupt numbers, clocks etc., should end up
in a separate header file that describes the entire chip rather than the
individual function blocks. The driver for a function block would have no need
for including this chip-level header.

This means that the information contained in the SVD needs to be rearranged
before generating headers. Redundancy needs to be removed, and chip-level
information needs to be collected from across all peripherals described in it.

### Missing information

The SVD file, owing to its purpose as a data source for debuggers, misses some
information that would be useful for programming. Most prominently, this
concerns the clock tree of a chip. Similarly, the buses and power domains are
usually not decribed, either. This hinders implementing generic code for
determining operating frequencies, enabling/disabling clocks selectively, or
power up/down certain parts of the chip.

Depending on the manufacturer, different amounts of information is given for
registers. Sometimes different values for a bitfield are properly described,
sometimes this information is omitted. Sometimes a textual description is given,
sometimes it is missing. In practice, a way of adding such missing information
is needed.

### No Multi-CPU support

The SVD file represents the view of one CPU on the set of peripherals on the
chip. Chips with multiple CPUs are becoming more common, and the way of SVD to
deal with that is by providing a separate file for each CPU. This leads to yet
more information repetition, and it doesn't cover any information about how
the CPUs are interconnected on chip. What's missing is a data structure that
can represent the view on the entire system with all CPUs together.

### No off-chip peripherals

Representing the off-chip hardware structure is not covered by SVD. Writing
software drivers for off-chip peripherals is just as desirable as for on-chip
peripherals, so a flexible data structure could be used for expanding the
description to the board level.

### Unclear versioning and error correction

The SVD files have no authoritative place for getting the most up-to-date
version, as they are usually provided by the chip manufacturer, and each
manufacturer has his own way of providing the files. As a result, different
versions often circulate that differ slightly, with no clear information which
one is best. They also often contain errors that vary between the versions.

It is therefore preferable to keep the SVD files in a versioned repository,
where you can refer to a certain version explicitly.

## The case for an intermediate format

What's needed is a data structure that more directly corresponds to the modular
approach a chip manufacturer takes when assembling the design of a chip. It
needs to support a superset of information relative to SVD, so that an SVD file
could be generated from the data, but for the other direction, some further data
would have to be added.

The various downsides of the SVD file call for an intermediate data
representation that is better suited for automatic header generation. This
intermediate format should be derived automatically or semi-automatically from
the SVD information, and possibly extra data sources. The point is that header
generation from the intermediate format should be automatic. Any data massaging
should be done before.

The intermediate format should therefore be suitable for object representation,
including references to other objects, possibly in other files. It should be
readable and editable by humans, suitable for patching and merging, reasonably
compact, support embedded comments, based on UTF-8, and extendable to cover
future needs.

YAML is a good candidate.

We hold a library of such YAML files in a versioned repository. We also provide
tools to generate the YAML files from SVD files and/or other sources. We can use
other people's tools to some advantage, e.g.:

<https://github.com/homeport/dyff>

Ideally, it should be possible to automatically create a valid SVD file from the
YAML files. In this way, a debugger can take advantage of the fixes provided for
the YAML files.

There is a Rust-based project that defines a YAML scheme for providing patch
information for SVD files, and tools for working with that. This might be a good
starting point:

<https://github.com/rust-embedded/svdtools>
