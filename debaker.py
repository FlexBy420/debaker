import os
import struct
import sys

class CoalescedTool:
    def __init__(self, debug=False):
        self.files = 0
        self.nmlen = 0
        self.secCount = 0
        self.recCount = 0
        self.valueLength = 0
        self.fullpath = ""
        self.debug = debug

    def read_int_be(self, f):
        data = f.read(4)
        if len(data) < 4:
            raise EOFError("Unexpected EOF while reading int")
        val = struct.unpack('>i', data)[0]
        if self.debug:
            print(f"[DEBUG] read_int_be: {val}")
        return val

    def read_name_length_be(self, f):
        raw_len = self.read_int_be(f)
        if raw_len < 0:
            length_bytes = (-raw_len - 1) * 2
            style = "NEG"
        else:
            length_bytes = raw_len
            style = "POS"

        if self.debug:
            print(f"[DEBUG] Name length raw={raw_len} style={style} bytes={length_bytes}")
        return length_bytes

    def read_value_length_be(self, f):
        raw_len = self.read_int_be(f)
        if raw_len < 0:
            val_len = -raw_len - 1
            style = "NEG"
        else:
            val_len = raw_len
            style = "POS"

        if self.debug:
            print(f"[DEBUG] Value length raw={raw_len} style={style} chars={val_len}")
        return val_len

    def decode_name(self, name_bytes):
        try:
            return name_bytes.decode('utf-16le')
        except UnicodeDecodeError:
            try:
                return name_bytes.decode('latin-1')
            except UnicodeDecodeError:
                return name_bytes.decode('utf-8', errors='replace')

    def validate_coalesced(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                self.files = self.read_int_be(f)
                self.nmlen = self.read_name_length_be(f)
                name_bytes = f.read(self.nmlen)
                self.fullpath = self.decode_name(name_bytes)

                if self.debug:
                    print(f"[DEBUG] files={self.files}, fullpath={self.fullpath}")

                if self.files == 0 or self.files > 10000:
                    print("Probably not a Coalesced file.")
                    return False
                return True
        except Exception as e:
            print(f"Validation error: {e}")
            return False

    def unpack(self, input_file, output_dir=None):
        if not output_dir:
            output_dir = os.path.splitext(os.path.basename(input_file))[0]

        os.makedirs(output_dir, exist_ok=True)

        with open(input_file, 'rb') as f:
            self.files = self.read_int_be(f)

            for file_index in range(self.files):
                self.nmlen = self.read_name_length_be(f)
                if self.nmlen < 1:
                    print(f"File name error at position {f.tell()}")
                    return

                self.fullpath = self.decode_name(f.read(self.nmlen))
                f.seek(2, os.SEEK_CUR)  # Skip null terminator (2 bytes)

                self.secCount = self.read_int_be(f)

                if self.nmlen > 0:
                    clean_path = self.fullpath.replace('..\\..\\', '')
                    full_output_path = os.path.join(output_dir, clean_path)
                    os.makedirs(os.path.dirname(full_output_path), exist_ok=True)

                    with open(full_output_path, 'w', encoding='utf-8') as out_file:
                        for sec_index in range(self.secCount):
                            sec_name_len = self.read_name_length_be(f)
                            sec_name_bytes = f.read(sec_name_len)
                            section_name = sec_name_bytes.decode('utf-16le')
                            f.seek(2, os.SEEK_CUR)  # skip null terminator

                            out_file.write(f'[{section_name}]\n')

                            self.recCount = self.read_int_be(f)

                            for _ in range(self.recCount):
                                key_name_len = self.read_name_length_be(f)
                                key_name_bytes = f.read(key_name_len)
                                key_name = key_name_bytes.decode('utf-16le')
                                f.seek(2, os.SEEK_CUR)  # skip null terminator

                                out_file.write(f"{key_name}=")

                                self.valueLength = self.read_value_length_be(f)
                                if self.valueLength > 0:
                                    value_chars = []
                                    for _ in range(self.valueLength):
                                        char_bytes = f.read(2)
                                        if char_bytes == b'\n\x00':
                                            value_chars.append('\u00B6')  # ¶ symbol
                                        else:
                                            value_chars.append(char_bytes.decode('utf-16le'))
                                    f.seek(2, os.SEEK_CUR)  # skip null terminator

                                    value = ''.join(value_chars).rstrip('\r\n')
                                    out_file.write(value)

                                out_file.write('\n')

                            if sec_index != self.secCount - 1:
                                out_file.write('\n')

    def repack(self, input_dir, output_file=None):
        if not output_file:
            output_file = os.path.join(input_dir, os.path.basename(input_dir) + '.bin')

        input_files = []
        for root, _, files in os.walk(input_dir):
            for file in files:
                rel_path = os.path.relpath(os.path.join(root, file), input_dir)
                input_files.append(rel_path.replace('\\', '\\'))

        self.files = len(input_files)

        with open(output_file, 'wb') as out_f:
            out_f.write(struct.pack('>i', self.files))

            for rel_path in input_files:
                full_input_path = os.path.join(input_dir, rel_path)
                bin_path = '..\\..\\' + rel_path.replace('/', '\\')

                name_len = len(bin_path)
                out_f.write(struct.pack('>i', -(name_len + 1)))
                out_f.write(bin_path.encode('utf-16le'))
                out_f.write(b'\x00\x00')

                with open(full_input_path, 'rb') as in_f:
                    content = in_f.read().decode('utf-16le', errors='replace')

                sections = content.split('\r\n\r\n')
                self.secCount = len([s for s in sections if s.strip()])
                out_f.write(struct.pack('>i', self.secCount))

                for section in sections:
                    if not section.strip():
                        continue

                    lines = section.split('\r\n')
                    if not lines:
                        continue

                    section_header = lines[0]
                    if section_header.startswith('[') and section_header.endswith(']'):
                        section_name = section_header[1:-1]
                        name_len = len(section_name)
                        out_f.write(struct.pack('>i', -(name_len + 1)))
                        out_f.write(section_name.encode('utf-16le'))
                        out_f.write(b'\x00\x00')

                        records = [line for line in lines[1:] if '=' in line]
                        self.recCount = len(records)
                        out_f.write(struct.pack('>i', self.recCount))

                        for record in records:
                            key, value = record.split('=', 1)
                            name_len = len(key)
                            out_f.write(struct.pack('>i', -(name_len + 1)))
                            out_f.write(key.encode('utf-16le'))
                            out_f.write(b'\x00\x00')

                            value = value.replace('¶', '\n')
                            value_len = len(value)
                            out_f.write(struct.pack('>i', -(value_len + 1)))
                            for char in value:
                                out_f.write(char.encode('utf-16le'))
                            out_f.write(b'\x00\x00')

def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  To unpack: py debaker.py unpack <input_file.bin> [output_dir] [--debug]")
        print("  To repack: py debaker.py repack <input_dir> [output_file.bin] [--debug]")
        return

    debug = '--debug' in sys.argv
    if debug:
        sys.argv.remove('--debug')

    tool = CoalescedTool(debug=debug)
    command = sys.argv[1].lower()

    if command == "unpack":
        input_file = sys.argv[2]
        output_dir = sys.argv[3] if len(sys.argv) > 3 else None

        if not tool.validate_coalesced(input_file):
            print("Invalid Coalesced file")
            return

        print(f"Unpacking {input_file}...")
        tool.unpack(input_file, output_dir)
        print("Unpacking completed!")

    elif command == "repack":
        input_dir = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else None

        print(f"Repacking {input_dir}...")
        tool.repack(input_dir, output_file)
        print("Repacking completed!")

    else:
        print("Invalid command. Use 'unpack' or 'repack'.")

if __name__ == "__main__":
    main()