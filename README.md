# Debaker

**Debaker** is a Python script designed to unpack and repack `Coalesced_xxx.bin` files, commonly found in Unreal Engine 3-based titles.

[![Wiki](https://img.shields.io/badge/Wiki-Supported_Games-blue.svg)](https://github.com/FlexBy420/debaker/wiki/Supported-Games)

## Overview
Many UE3 games bundle configuration and language files into a single `Coalesced_xxx.bin` archive. Debaker allows you to extract these files and repack them back into the original binary format while maintaining strict adherence to the required data structures.

## Usage

### Prerequisites
* [Python 3.x](https://www.python.org/)

### Commands
Execute the script using the following syntax:

```bash
# Unpack a Coalesced.bin file
py debaker.py unpack <input_file.bin> [output_dir] [--debug]

# Repack a folder back into a .bin file
py debaker.py repack <input_dir> [output_file.bin] [--debug]
