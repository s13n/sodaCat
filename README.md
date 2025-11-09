# sodaCat

SodaCat maintains a database of chip information for microcontrollers,
systems-on-chip, and similar hardware. The database is mainly aimed at
supporting automatic code generation, for example generating C or C++ header
files for supporting driver development. It is a work in progress, not yet
stable.

The tools you can find here are helpers to generate and maintain the data in the
database. The database itself consists of YAML files contained in the directory
tree below `data`. You use the database by using one or several of those YAML
files in your own project.

There are example code generation tools included here that generates C++20 files
from those YAML files. One tool generates a header for a peripheral, and another
tool generates a header for an SoC. They are included to illustrate how to do
generation, and thus help you write your custom generator tools, but they can be
used as-is if you are satisfied with the output they create. Header generation
is described in [this page](Header-generation.md).

## How to use this database

The process typically involves two steps:

1. Generate data models of the chip and its function blocks as YAML files.
2. Use those data models to automatically generate code for use in your project.

The first step might have been done already, and you can access the models in
the `models` subdirectory. If not, you may have to either use a parser from
those in the `parsers` directory, or write one for the device family you're
interested in. Such a parser would typically be a python script that uses some
sort of manufacturer provided data file and extract the model from it, often
applying further patches or alterations to the data, before dumping the model
into YAML files.

The second step involves running a generator to convert the models into source
files for your preferred programming language. A generator for C++ is provided
in the `generators` directory, further generators might get added over time. If
you are not happy with the style of the code the generator produces, you are
free to write your own. Note that if only the formatting needs to be changed,
there are separate tools for that, for example `clang-format` for C++.

The assumption is that you integrate the generation step into your build system,
for example as CMake targets if that is what you use. This allows you to
automatically take advantage of updated models or generators. The build system
might fetch the relevant model files from the sodaCat repository and store the
generated source files among the build artefacts. See also
[this description](generators/README.md).

If you need to write your own parser, you can follow the respective task
descriptions in the `tasks` directory. Those are intended to be used with AI
agents, but can also be followed manually. See the respective
[description](tasks/README.md).

## The underlying philosophy of the database

This database contains separate YAML model files for individual function blocks
used in chips, and additional YAML files for tying those blocks together to form
a complete chip, or even a board-level system. The way the function blocks are
instantiated and interconnected in hardware, mimicks the way the model files are
combined to describe a complete system.

The database doesn't care how you use the information to create code, so it is
language agnostic and doesn't prescribe any format or naming convention. You are
free to write your own generator, implementing the style and conventions you
prefer.

You should typically only need a single YAML file for implementing a driver for
the corresponding function block, as the driver, in order to be generic, will
only need the data for the respective function block. This means that the driver
will have to be parameterized with information about its integration into the
chip or system. This integration information will have to be passed to the
driver on instantiation. At the very least, this would include the location of
the function block's registers in the address space of the CPU that runs the
driver code. This integration data would be contained in a different YAML file,
which would be used by the code that instantiates and parameterizes the driver.

## Function block parameterization

Sometimes function blocks come in variants. While the variants share lots of
commonalities, not least a common register model, they may differ in the set of
features actually implemented on the chip. For example, a timer implementation
may vary in the number of capture/compare channels implemented in a specific
instantiation. Sometimes that even happens on the same chip, where one timer has
4 of those channels, and another only two, or whatever other number, but
otherwise they're the same. It would make sense to exploit the commonality for
having a common driver, but that driver would have to be parameterized with the
number of channels actually implemented. The same applies to the model file for
the timer: It would have to have a means to parameterize it from the outside, so
that the same file would apply to both variants of the implementation.

Such parameters might be flags that indicate whether a particular feature is
implemented or not. Or it may be a number that indicates how many instances of a
certain subfunction are implemented (e.g. channels). Multiple such parameters
may exist for a function block, and those externally supplied parameters would
apply to the data file, and also to the driver.

## Models folder structure

The models folder is organized according to manufacturer. If a function block is
known to have been developed by a different company than the chip manufacturer,
its data file should be placed in the directory of its developer. Sometimes chip
manufacturers don't make this information public, and the data file must be
placed into the chip manufacturer's folder. Of course, the developer of the CPU
function block is usually known, for example ARM, and the respective data files
will be found in their folder.

A chip manufacturer may have developed both chips and function blocks, and in
this case both the chip-specific files, and the function block specific files,
would be found in the same folder.

Quite frequently, in both the reference manuals and in the SVD files of chips,
the manufacturer uses generic names for certain function blocks. For example, it
happens that for two different chips by the same manufacturer, their USB
function blocks are merely called `USB`, even though the functionality is quite
different between them, and a common data file to describe them both is out of
the question. You will then have to come up with two differently named data
files for the different function blocks. Sometimes the manufacturer uses an
internal code name for the function block, which can be found in the
documentation. Then you can use this code name as the file name. Otherwise you
will have to come up with your own way of disambiguating the file names.

Along with the YAML files, the `parsers` folder also may contain script files
that are used to generate the YAML files. Those script files typically contain
code to fetch the original data, for example an SVD file, and process it to
generate one or more YAML files. The script file may also contain code to modify
or add information coming from the original data sources. This is to correct
errors, add missing information, and rearrange existing data to make it conform
to the data model defined here. You would not normally need to run the scripts
yourself, as the result is already in the repository. Only when adding new
files, or fixing errors, you would need to touch the scripts. Of course, you may
use existing scripts as examples for writing your own.

## Supporting generic drivers

For a generic driver, you need a header file describing the register set for the
corresponding peripheral. Header generation is done via a script that reads the
YAML file of the peripheral, and turns it into C or C++ source code. See
[here](generators/README.md) for the details.

When writing a generic driver for a function block that can come with a varying
feature set, you would usually use the data file of the variant with all
features present. This data file would contain definitions for all registers
that pertain to all features. In variants with missing features, some registers,
or some bitfields, will therefore not exist.

The driver needs to know which features are implemented in the peripheral it is
instantiated for. If this can't be autodetected, the driver needs to be
parameterized accordingly on instantiation. Depending on those parameters, the
driver will have to refrain from accessing registers or bitfields that don't
exist. This needs to be ensured by the driver writer, the generator can't help
here.

Suitable data files with all features present can usually be generated from the
most feature rich, and/or most recent chips within a series. As an alternative,
information from several chips may habe to be combined. You will need to verify,
however, if the register maps really match.

You will need to identify what parameters there are, which will distinguish the
feature variants between different implementations. Those will have to be listed
in the data file.

## Why not just use SVD files?

The common way of obtaining chip data suitable for generating code is from ARM
["System View
Description"](https://open-cmsis-pack.github.io/svd-spec/main/index.html) files.
Chip manufacturers using processor cores from ARM typically create such files
for their products. They originally were devised for helping debuggers display
the contents of the registers in a chip. The definition has since been upgraded
to better support code generation, too. Tools for doing this have been provided
from multiple sources, including ARM itself.

However, SVD files have a number of drawbacks, and we use them here for data
mining and automatic or semi-automatic generation of YAML files for our
database. Details of that process are described [here](svd/README.md).

Furthermore not every manufacturer supports SVD files. For example, Texas
Instruments use their own XML-based data format for describing SoC hardware.
Here, there are separate files for each functional block, or "Module" as TI
calls it, and a further file that ties them together into a SoC device. This is
much closer to the philosophy of this database here. Details of how to generate
YAML files from this format are described [here](models/TI/README.md).

# Appendix: Interesting external projects

- https://github.com/modm-io/modm-data Tools for extracting hardware description
  info from various inputs, e.g. PDF data sheets
