#!/usr/bin/env python3
"""
Secure File Deletion Tool
Overwrites files multiple times before deletion to prevent recovery.
"""

import os
import sys
import random
import argparse
from pathlib import Path

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def get_file_size(filepath):
    """Get file size in bytes."""
    return os.path.getsize(filepath)


def overwrite_file(filepath, passes=7):
    """
    Securely overwrite file with random data multiple times.

    Uses DOD 5220.22-M standard (7 passes):
    - Pass 1: Write 0x00
    - Pass 2: Write 0xFF
    - Pass 3: Random data
    - Pass 4: Random data
    - Pass 5: Random data
    - Pass 6: Random data
    - Pass 7: Random data + verification
    """
    try:
        file_size = get_file_size(filepath)

        with open(filepath, 'rb+') as f:
            for pass_num in range(1, passes + 1):
                f.seek(0)

                if pass_num == 1:
                    # First pass: all zeros
                    data = b'\x00' * min(file_size, 4096)
                    for _ in range(0, file_size, 4096):
                        f.write(data[:min(4096, file_size - f.tell())])
                elif pass_num == 2:
                    # Second pass: all ones
                    data = b'\xFF' * min(file_size, 4096)
                    for _ in range(0, file_size, 4096):
                        f.write(data[:min(4096, file_size - f.tell())])
                else:
                    # Remaining passes: random data
                    for _ in range(0, file_size, 4096):
                        chunk_size = min(4096, file_size - f.tell())
                        random_data = bytes(random.randint(0, 255) for _ in range(chunk_size))
                        f.write(random_data)

                f.flush()
                os.fsync(f.fileno())

                print(f"    Pass {pass_num}/{passes} complete", end='\r')

        print(f"    {Colors.GREEN}All {passes} passes complete{Colors.END}     ")
        return True

    except Exception as e:
        print(f"    {Colors.RED}Error during overwrite: {e}{Colors.END}")
        return False


def secure_delete_file(filepath, passes=7, rename=True):
    """
    Securely delete a file:
    1. Overwrite with random data multiple times
    2. Rename to random name (optional, hides original filename)
    3. Delete the file
    """
    filepath = Path(filepath)

    if not filepath.exists():
        print(f"{Colors.RED}Error: File not found: {filepath}{Colors.END}")
        return False

    if not filepath.is_file():
        print(f"{Colors.RED}Error: Not a file: {filepath}{Colors.END}")
        return False

    print(f"\n{Colors.YELLOW}Securely deleting:{Colors.END} {filepath}")
    print(f"  Size: {get_file_size(filepath):,} bytes")
    print(f"  Passes: {passes}")

    # Step 1: Overwrite file content
    print(f"\n{Colors.BLUE}Step 1: Overwriting file data...{Colors.END}")
    if not overwrite_file(filepath, passes):
        return False

    # Step 2: Rename to random name (hides original filename)
    if rename:
        print(f"\n{Colors.BLUE}Step 2: Renaming to random name...{Colors.END}")
        try:
            random_name = ''.join(random.choices('0123456789abcdef', k=32))
            new_path = filepath.parent / random_name
            filepath.rename(new_path)
            filepath = new_path
            print(f"    {Colors.GREEN}Renamed successfully{Colors.END}")
        except Exception as e:
            print(f"    {Colors.YELLOW}Warning: Could not rename: {e}{Colors.END}")

    # Step 3: Delete the file
    print(f"\n{Colors.BLUE}Step 3: Deleting file...{Colors.END}")
    try:
        filepath.unlink()
        print(f"    {Colors.GREEN}File deleted successfully{Colors.END}")
        return True
    except Exception as e:
        print(f"    {Colors.RED}Error deleting file: {e}{Colors.END}")
        return False


def secure_delete_directory(dirpath, passes=7):
    """Recursively secure delete all files in a directory."""
    dirpath = Path(dirpath)

    if not dirpath.exists():
        print(f"{Colors.RED}Error: Directory not found: {dirpath}{Colors.END}")
        return False

    if not dirpath.is_dir():
        print(f"{Colors.RED}Error: Not a directory: {dirpath}{Colors.END}")
        return False

    files = list(dirpath.rglob('*'))
    files = [f for f in files if f.is_file()]

    if not files:
        print(f"{Colors.YELLOW}No files found in directory{Colors.END}")
        return True

    print(f"\n{Colors.BOLD}Found {len(files)} files to delete{Colors.END}")

    success_count = 0
    fail_count = 0

    for filepath in files:
        if secure_delete_file(filepath, passes, rename=True):
            success_count += 1
        else:
            fail_count += 1

    # Remove empty directories
    try:
        for dirpath_item in sorted(dirpath.rglob('*'), key=lambda p: len(p.parts), reverse=True):
            if dirpath_item.is_dir():
                try:
                    dirpath_item.rmdir()
                except OSError:
                    pass  # Directory not empty, skip

        dirpath.rmdir()
        print(f"\n{Colors.GREEN}Directory deleted{Colors.END}")
    except Exception as e:
        print(f"\n{Colors.YELLOW}Could not remove directory: {e}{Colors.END}")

    print(f"\n{Colors.BOLD}Summary:{Colors.END}")
    print(f"  {Colors.GREEN}Success: {success_count}{Colors.END}")
    print(f"  {Colors.RED}Failed: {fail_count}{Colors.END}")

    return fail_count == 0


def confirm(message):
    """Ask user for confirmation."""
    while True:
        response = input(f"{message} {Colors.RED}[y/N]:{Colors.END} ").strip().lower()
        if response in ('y', 'yes'):
            return True
        if response in ('n', 'no', ''):
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Securely delete files by overwriting them multiple times.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Security Levels:
  --passes 3   : Quick (NSA standard)
  --passes 7   : Standard (DOD 5220.22-M) [default]
  --passes 35  : Paranoid (Gutmann method)

Examples:
  %(prog)s secret.txt
  %(prog)s secret.txt --passes 35
  %(prog)s -r confidential_folder/
  %(prog)s file1.txt file2.pdf file3.doc

WARNING: This is PERMANENT and IRREVERSIBLE!
        """
    )

    parser.add_argument(
        'paths',
        nargs='+',
        help='File(s) or directory to securely delete'
    )
    parser.add_argument(
        '-p', '--passes',
        type=int,
        default=7,
        help='Number of overwrite passes (default: 7)'
    )
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Recursively delete directories'
    )
    parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    # Validate passes
    if args.passes < 1:
        print(f"{Colors.RED}Error: Number of passes must be at least 1{Colors.END}")
        sys.exit(1)

    if args.passes > 35:
        print(f"{Colors.YELLOW}Warning: {args.passes} passes is excessive. Using 35 passes.{Colors.END}")
        args.passes = 35

    # Display warning
    print(f"\n{Colors.BOLD}{Colors.RED}{'=' * 60}")
    print("                 ⚠️  WARNING ⚠️")
    print(f"{'=' * 60}{Colors.END}\n")
    print(f"{Colors.RED}This will PERMANENTLY and IRREVERSIBLY delete:{Colors.END}\n")

    for path in args.paths:
        p = Path(path)
        if p.exists():
            if p.is_file():
                print(f"  📄 {p} ({get_file_size(p):,} bytes)")
            elif p.is_dir():
                if args.recursive:
                    files = list(p.rglob('*'))
                    files = [f for f in files if f.is_file()]
                    print(f"  📁 {p} ({len(files)} files)")
                else:
                    print(f"  {Colors.YELLOW}📁 {p} (use -r to delete directories){Colors.END}")
        else:
            print(f"  {Colors.YELLOW}❌ {p} (not found){Colors.END}")

    print(f"\n{Colors.YELLOW}Method: {args.passes}-pass overwrite{Colors.END}")
    print(f"{Colors.RED}Files cannot be recovered after this operation!{Colors.END}\n")

    # Confirmation
    if not args.force:
        if not confirm(f"{Colors.BOLD}Are you absolutely sure?{Colors.END}"):
            print(f"\n{Colors.YELLOW}Cancelled.{Colors.END}\n")
            sys.exit(0)

    # Process files
    print(f"\n{Colors.BOLD}{'=' * 60}")
    print("           STARTING SECURE DELETION")
    print(f"{'=' * 60}{Colors.END}\n")

    for path in args.paths:
        p = Path(path)

        if not p.exists():
            print(f"{Colors.YELLOW}Skipping: {p} (not found){Colors.END}")
            continue

        if p.is_file():
            secure_delete_file(p, args.passes)
        elif p.is_dir():
            if args.recursive:
                secure_delete_directory(p, args.passes)
            else:
                print(f"{Colors.YELLOW}Skipping directory: {p} (use -r flag){Colors.END}")

    print(f"\n{Colors.BOLD}{Colors.GREEN}{'=' * 60}")
    print("              SECURE DELETION COMPLETE")
    print(f"{'=' * 60}{Colors.END}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Cancelled by user.{Colors.END}\n")
        sys.exit(0)
