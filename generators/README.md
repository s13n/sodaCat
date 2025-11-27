# Header generation

Header generation is the generation of source code for programming languages
from the data models. Different languages are possible, such as C, C++ or Rust.
Other kinds of generation targets are also conceivable, such as debug support
files and documentation. The generators are python scripts in this folder.
Generators for each target language are in language-specific subfolders.

Generating a header from a YAML file requires some considerations which are to
be discussed here. The requirements can be summarized as follows:

- There should be a direct relationship between the names in the YAML file and
  the identifiers defined in the header, so that the relationship between the
  code and the chip data sheet or reference manual is obvious. Ideally, the
  names should be the same. Sometimes, however, names are encountered that can't
  be used as identifiers in a programming language, and the generator needs to
  make an intelligent choice.
- The names should not be unnecessarily verbose, yet the risk of name clashes or
  ambiguities should be as low as possible.
- The definitions in the header should be easy to use, and hard to accidentally
  misuse, so good use should be made of the compiler's type checking abilities.
  But the programmer must be allowed to do what needs to be done, even in odd
  cases, so nothing should be made excessively difficult.
- Accesses to registers should be clearly visible in the source code, especially
  for multiple accesses. Read-modify-write accesses should be obvious, and not
  hidden behind a compound assignment.
- Special access methods should be supported, i.e. register sets that are not
  directly mapped into the address space. This covers registers accessible via
  I2C or SPI busses, or processors with specialized instructions or instruction
  sequences for access to special registers. 

## Peripheral headers

A certain peripheral is usually reused a lot by a manufacturer. It may appear in
multiple instances on the same chip, and sometimes the instances have a
different feature set. It may also appear in different chips of a series, or
even across different series of chips. In some cases the peripheral is licensed
to chip designers, so that the same peripheral may even appear in chips of
different manufacturers. In all cases you want to be able to write common driver
code for all.

It should be possible to write a driver for the peripheral that is oblivious to
the chip into which it is integrated. Such a driver would get the base address
and the interrupt number from the outside at the time of instantiation, i.e. as
constructor arguments. The driver code shouldn't need to include the chip-level
header at all.

In the ideal case you have a YAML file for the superset of all variants,
describing all possible features. The driver will then need to be parameterized
with information about the features that are actually implemented. In our case,
those parameters are provided via a reference to a constexpr struct with the
parameters for a single instance of the peripheral.

The peripheral header contains definitions for the register set of the
peripheral, and a definition of the parameter struct (here called "integration
struct"). As a minimum, the integration struct contains a pointer to the
register set of the peripheral. But often this is augmented by feature presence
bits, interrupt/exception numbers and more. As the information in the
integration struct is constant, it can reside in read-only memory.

## Chip-level header

A chip consists of a CPU connected to memory blocks and a number of peripherals.
The peripherals are defined in their own headers, to facilitate reuse. All
information that is specific to their integration onto a particular chip is
defined in the chip-level header. Information that belongs there are:

- Base address of each peripheral

Optionally:

- Interrupt numbers / interrupt vectors
- DMA request interconnects
- Clock signals feeding the peripheral
- Other signaling between functional blocks, such as event or wakeup
  interconnects
- Feature implementation details

The aim of this kind of separation into distinct headers is to define the
peripherals in a way that is not tied to a particular instantiation. The
peripheral itself should be decribed, not the way it is integrated into a
chip. Hence the base address has no business being specified in a peripheral
header, and neither has the interrupt number and all the other parameters,
because they typically vary between different chips using the peripheral block.

This facilitates writing generic drivers for the peripheral that don't depend on
the chip-level header. The chip-level header should only be needed by code that
is specific to the chip as a whole. Typically this information is needed at
initialization time, when the various driver objects get instantiated.

Note that peripheral base addresses are usually declared as a pointer to the
`volatile` register struct of the peripheral. Making the pointer point to a
volatile struct ensures that for accesses to all registers the compiler refrains
from optimizing register accesses, so that the code doesn't show surprising
behavior.

In some cases, i.e. some registers, there would be no harm in omitting the
volatile and allowing the optimization, but this is fairly uncommon with
hardware registers, so the overall `volatile` on the pointer is actually the
most convenient declaration style. Otherwise the `volatile` would have to be
applied selectively to individual register declarations, which is much more
verbose. Furthermore, by appplying the `volatile` to the pointer, it is easy to
choose non-volatile accesses by merely using a different pointer type.

## Clock tree header

Microcontrollers have increasingly complex clock distribution infrastructure,
which includes multiple clock sources, and various gates, dividers, multiplexers
etc. to selectively feed clocks to function blocks. This structure can be
described by a separate YAML file, and from this a header can be generated,
which can trace the path of a clock signal to determine its frequency.
