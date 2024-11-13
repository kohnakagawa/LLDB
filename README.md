# LLDB

Some useful LLDB scripts for debugging

## Installation

```
git clone git@github.com:kohnakagawa/LLDB.git $HOME/lldb
echo "command script import $HOME/lldb/commands/lldbinit.py" >> $HOME/.lldbinit
mkdir -p $HOME/Documents/Resources/
git clone https://github.com/DerekSelander/LLDB.git $HOME/Documents/Resources/LLDB
echo "command script import $HOME/Documents/Resources/LLDB/lldb_commands/dslldb.py" >> $HOME/.lldbinit
rm $HOME/Documents/Resources/LLDB/lldb_commands/generate_new_script.py
```

## Author

Koh M. Nakagawa

## License

Apache version 2.0
