# LLDB

Some useful LLDB scripts for my macOS debugging

## Installation

```
git clone git@github.com:kohnakagawa/LLDB.git $HOME/lldb
echo "command script import $HOME/lldb/commands/lldbinit.py" >> $HOME/.lldbinit
mkdir -p $HOME/Documents/Resources/
git clone https://github.com/DerekSelander/LLDB.git $HOME/Documents/Resources/
echo "command script import $HOME/Documents/Resources/LLDB/lldb_commands/dslldb.py" >> $HOME/.lldbinit
rm $HOME/Documents/Resources/LLDB/lldb_commands/generate_new_script.py
```

## Defined commands

### `brt_set_bps`

**Summary**

Sets breakpoints at all indirect branch instructions (call/jmp) in the main module of the target program. This command is specifically designed for x86_64 processes and currently only supports the main module.

**Usage**

```
(lldb) brt_set_bps
```

**Details**

- Identifies all indirect branch instructions in the `__TEXT.__text` section
- Creates breakpoints at each identified instruction
- When a breakpoint is hit, it records:
    - Current module name
    - Function name
    - Values of all 64-bit general purpose registers
    - Destination address of the branch
- Collected data can be saved to a JSON file using the `brt_save` command

**Requirements**

This tool uses the radare2 tool to identify indirect branch instructions, so you need to install it first.

```
brew install radare2
```

### `brt_save`

**Summary**

Saves the collected branch trace data to a JSON file in the `/tmp` directory. The saved JSON file can be loaded through my [Binja Missing Link Plugin](https://github.com/FFRI/binja-missinglink).

**Usage**

```
(lldb) brt_save
```

### `swtt_set_bps`

**Summary**

Sets breakpoints on `swift_allocObject` and `swift_initStackObject` to obtain type metadata. Collected type metadata can be saved to a JSON file using the `swtt_save` command.

**Usage**

```
(lldb) swtt_set_bps
```

### `swtt_save`

**Summary**

Saves the collected type metadata to a JSON file in the `/tmp` directory. The saved JSON file can be loaded through our [Binja Swift Analyzer Plugin](https://github.com/FFRI/binja-swift-analyzer).

**Usage**

```
(lldb) swtt_save
```

### `sdump`

**Summary**

Prints the contents of a Swift object.

**Usage**

```
(lldb) sdump <object address>
```

### `p_boxed_array`, `po_boxed_array`, `dump_boxed_array`

**Summary**

Prints the contents of an existential container.

**Usage**

```
(lldb) p_boxed_array <object address>
(lldb) po_boxed_array <object address>
(lldb) dump_boxed_array <object address>
```

## Author

Koh M. Nakagawa (@tsunek0h)

## License

[Apache version 2.0](./LICENSE)
