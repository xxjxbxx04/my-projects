#!/usr/bin/env python3
"""
Home Directory Cleanup Tool
Finds and helps delete: duplicates, empty files/folders, junk files, large files, and old files.
"""

import os
import sys
import hashlib
import argparse
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Set, Tuple

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


# Directories to skip
SKIP_DIRS = {
    'Library', 'Applications', '.git', 'node_modules', '.ssh', '.config',
    '.Trash', '.npm', '.cargo', '.rustup', '.pyenv', '.nvm', '.rbenv',
    '.local', '.cache', '.vscode', '.idea', 'venv', '.venv', '__pycache__',
    '.gradle', '.m2', '.docker', 'Movies', 'Music', 'Pictures', 'Photos Library.photoslibrary'
}

# Junk file patterns
JUNK_EXTENSIONS = {
    '.tmp', '.temp', '.log', '.bak', '.old', '.swp', '.swo',
    '.DS_Store', '.Thumbs.db', '.thumbs.db', '.desktop.ini'
}

JUNK_NAMES = {
    '.DS_Store', 'Thumbs.db', 'desktop.ini', '.localized',
    '.CFUserTextEncoding', '.Spotlight-V100', '.fseventsd'
}

JUNK_PREFIXES = {'._', '~$', '.~'}


class CleanupScanner:
    def __init__(self, root_path: Path, large_threshold_mb: int = 100, old_days: int = 120):
        self.root_path = root_path
        self.large_threshold = large_threshold_mb * 1024 * 1024  # Convert to bytes
        self.old_threshold = datetime.now() - timedelta(days=old_days)
        self.old_days = old_days

        # Results
        self.duplicates: Dict[str, List[Path]] = defaultdict(list)
        self.empty_files: List[Path] = []
        self.empty_dirs: List[Path] = []
        self.junk_files: List[Path] = []
        self.large_files: List[Tuple[Path, int]] = []
        self.old_files: List[Tuple[Path, datetime]] = []

        # Stats
        self.files_scanned = 0
        self.dirs_scanned = 0
        self.total_size_scanned = 0

    def should_skip(self, path: Path) -> bool:
        """Check if path should be skipped."""
        for part in path.parts:
            if part in SKIP_DIRS:
                return True
        return False

    def is_junk_file(self, path: Path) -> bool:
        """Check if file is a junk file."""
        name = path.name
        suffix = path.suffix.lower()

        if name in JUNK_NAMES:
            return True
        if suffix in JUNK_EXTENSIONS:
            return True
        if name == '.DS_Store':
            return True
        for prefix in JUNK_PREFIXES:
            if name.startswith(prefix):
                return True
        return False

    def get_file_hash(self, filepath: Path, quick: bool = True) -> str:
        """Calculate file hash. Quick mode only hashes first/last 4KB."""
        hasher = hashlib.md5()
        try:
            file_size = filepath.stat().st_size
            with open(filepath, 'rb') as f:
                if quick and file_size > 8192:
                    # Hash first 4KB
                    hasher.update(f.read(4096))
                    # Hash last 4KB
                    f.seek(-4096, 2)
                    hasher.update(f.read(4096))
                    # Include size in hash for quick mode
                    hasher.update(str(file_size).encode())
                else:
                    # Hash entire file for small files
                    for chunk in iter(lambda: f.read(65536), b''):
                        hasher.update(chunk)
            return hasher.hexdigest()
        except (IOError, OSError):
            return ""

    def scan(self) -> None:
        """Scan the directory for cleanup candidates."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}Scanning {self.root_path}...{Colors.END}\n")

        # First pass: collect all files
        all_files: List[Tuple[Path, int, datetime]] = []

        for root, dirs, files in os.walk(self.root_path):
            root_path = Path(root)

            # Skip excluded directories
            if self.should_skip(root_path):
                dirs.clear()
                continue

            # Filter out skip dirs from traversal
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            self.dirs_scanned += 1

            # Check for empty directory
            if not dirs and not files:
                self.empty_dirs.append(root_path)

            # Process files
            for filename in files:
                filepath = root_path / filename

                try:
                    stat = filepath.stat()
                    file_size = stat.st_size
                    mtime = datetime.fromtimestamp(stat.st_mtime)

                    self.files_scanned += 1
                    self.total_size_scanned += file_size

                    # Progress indicator
                    if self.files_scanned % 500 == 0:
                        print(f"  Scanned {self.files_scanned:,} files...", end='\r')

                    all_files.append((filepath, file_size, mtime))

                    # Check categories
                    if file_size == 0:
                        self.empty_files.append(filepath)
                    elif self.is_junk_file(filepath):
                        self.junk_files.append(filepath)
                    else:
                        # Check for large files
                        if file_size >= self.large_threshold:
                            self.large_files.append((filepath, file_size))

                        # Check for old files
                        if mtime < self.old_threshold:
                            self.old_files.append((filepath, mtime))

                except (IOError, OSError, PermissionError):
                    continue

        print(f"  Scanned {self.files_scanned:,} files in {self.dirs_scanned:,} directories")

        # Second pass: find duplicates (only for non-empty, non-junk files > 1KB)
        print(f"\n{Colors.CYAN}Finding duplicates...{Colors.END}")

        # Group by size first (quick filter)
        size_groups: Dict[int, List[Tuple[Path, datetime]]] = defaultdict(list)
        for filepath, file_size, mtime in all_files:
            if file_size > 1024 and not self.is_junk_file(filepath):
                size_groups[file_size].append((filepath, mtime))

        # For files with same size, compare hashes
        hash_count = 0
        potential_dups = [(size, files) for size, files in size_groups.items() if len(files) > 1]

        for size, files in potential_dups:
            hash_groups: Dict[str, List[Tuple[Path, datetime]]] = defaultdict(list)

            for filepath, mtime in files:
                file_hash = self.get_file_hash(filepath)
                if file_hash:
                    hash_groups[file_hash].append((filepath, mtime))
                    hash_count += 1
                    if hash_count % 100 == 0:
                        print(f"  Hashed {hash_count:,} potential duplicates...", end='\r')

            # Files with same hash are duplicates
            for file_hash, dup_files in hash_groups.items():
                if len(dup_files) > 1:
                    # Sort by mtime (newest first) - we'll keep the newest
                    dup_files.sort(key=lambda x: x[1], reverse=True)
                    self.duplicates[file_hash] = [f[0] for f in dup_files]

        print(f"  Hashed {hash_count:,} files for duplicate detection")

        # Sort results
        self.large_files.sort(key=lambda x: x[1], reverse=True)
        self.old_files.sort(key=lambda x: x[1])

    def format_size(self, size: int) -> str:
        """Format size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def format_age(self, mtime: datetime) -> str:
        """Format file age."""
        age = datetime.now() - mtime
        if age.days > 365:
            years = age.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif age.days > 30:
            months = age.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        else:
            return f"{age.days} days ago"

    def get_duplicate_size(self) -> int:
        """Calculate total size of duplicate files (excluding originals)."""
        total = 0
        for files in self.duplicates.values():
            for filepath in files[1:]:  # Skip first (newest, kept)
                try:
                    total += filepath.stat().st_size
                except:
                    pass
        return total

    def print_summary(self) -> None:
        """Print summary of findings."""
        print(f"\n{Colors.BOLD}{'=' * 70}")
        print(f"                         SCAN SUMMARY")
        print(f"{'=' * 70}{Colors.END}\n")

        print(f"  {Colors.CYAN}Total scanned:{Colors.END} {self.files_scanned:,} files, {self.format_size(self.total_size_scanned)}")
        print()

        categories = [
            ("1", "Duplicate files", len(self.duplicates), self.get_duplicate_size(), Colors.RED),
            ("2", "Empty files", len(self.empty_files), 0, Colors.YELLOW),
            ("3", "Empty directories", len(self.empty_dirs), 0, Colors.YELLOW),
            ("4", "Junk files", len(self.junk_files), sum(f.stat().st_size for f in self.junk_files if f.exists()), Colors.MAGENTA),
            ("5", "Large files (>100MB)", len(self.large_files), sum(s for _, s in self.large_files), Colors.BLUE),
            ("6", f"Old files (>{self.old_days} days)", len(self.old_files), sum(f.stat().st_size for f, _ in self.old_files if f.exists()), Colors.GREEN),
        ]

        for num, name, count, size, color in categories:
            if count > 0:
                size_str = f" ({self.format_size(size)})" if size > 0 else ""
                print(f"  {Colors.BOLD}[{num}]{Colors.END} {color}{name}:{Colors.END} {count:,} items{size_str}")
            else:
                print(f"  {Colors.DIM}[{num}] {name}: None found{Colors.END}")

        print()

    def print_category_details(self, category: str, limit: int = 20) -> None:
        """Print details for a specific category."""
        if category == "1" and self.duplicates:
            print(f"\n{Colors.BOLD}{Colors.RED}DUPLICATE FILES{Colors.END}")
            print(f"{Colors.DIM}(First file in each group will be KEPT, others deleted){Colors.END}\n")

            shown = 0
            for file_hash, files in list(self.duplicates.items())[:limit]:
                size = self.format_size(files[0].stat().st_size) if files[0].exists() else "?"
                print(f"  {Colors.GREEN}[KEEP]{Colors.END} {files[0]}")
                for dup in files[1:]:
                    print(f"  {Colors.RED}[DEL]{Colors.END}  {dup}")
                print(f"  {Colors.DIM}Size: {size}{Colors.END}\n")
                shown += 1

            if len(self.duplicates) > limit:
                print(f"  {Colors.DIM}... and {len(self.duplicates) - limit} more duplicate groups{Colors.END}\n")

        elif category == "2" and self.empty_files:
            print(f"\n{Colors.BOLD}{Colors.YELLOW}EMPTY FILES{Colors.END}\n")
            for f in self.empty_files[:limit]:
                print(f"  {f}")
            if len(self.empty_files) > limit:
                print(f"  {Colors.DIM}... and {len(self.empty_files) - limit} more{Colors.END}")
            print()

        elif category == "3" and self.empty_dirs:
            print(f"\n{Colors.BOLD}{Colors.YELLOW}EMPTY DIRECTORIES{Colors.END}\n")
            for d in self.empty_dirs[:limit]:
                print(f"  {d}")
            if len(self.empty_dirs) > limit:
                print(f"  {Colors.DIM}... and {len(self.empty_dirs) - limit} more{Colors.END}")
            print()

        elif category == "4" and self.junk_files:
            print(f"\n{Colors.BOLD}{Colors.MAGENTA}JUNK FILES{Colors.END}\n")
            for f in self.junk_files[:limit]:
                size = self.format_size(f.stat().st_size) if f.exists() else "?"
                print(f"  {f} {Colors.DIM}({size}){Colors.END}")
            if len(self.junk_files) > limit:
                print(f"  {Colors.DIM}... and {len(self.junk_files) - limit} more{Colors.END}")
            print()

        elif category == "5" and self.large_files:
            print(f"\n{Colors.BOLD}{Colors.BLUE}LARGE FILES (>100MB){Colors.END}\n")
            for f, size in self.large_files[:limit]:
                print(f"  {self.format_size(size):>10}  {f}")
            if len(self.large_files) > limit:
                print(f"  {Colors.DIM}... and {len(self.large_files) - limit} more{Colors.END}")
            print()

        elif category == "6" and self.old_files:
            print(f"\n{Colors.BOLD}{Colors.GREEN}OLD FILES (>{self.old_days} days){Colors.END}\n")
            for f, mtime in self.old_files[:limit]:
                age = self.format_age(mtime)
                size = self.format_size(f.stat().st_size) if f.exists() else "?"
                print(f"  {age:>18}  {size:>10}  {f}")
            if len(self.old_files) > limit:
                print(f"  {Colors.DIM}... and {len(self.old_files) - limit} more{Colors.END}")
            print()

    def get_files_for_category(self, category: str) -> List[Path]:
        """Get list of files to delete for a category."""
        if category == "1":
            # For duplicates, return all but the newest (first) in each group
            files = []
            for file_list in self.duplicates.values():
                files.extend(file_list[1:])
            return files
        elif category == "2":
            return self.empty_files
        elif category == "3":
            return self.empty_dirs
        elif category == "4":
            return self.junk_files
        elif category == "5":
            return [f for f, _ in self.large_files]
        elif category == "6":
            return [f for f, _ in self.old_files]
        return []


class Cleaner:
    def __init__(self, backup_dir: Path = None):
        self.backup_dir = backup_dir
        self.deleted_count = 0
        self.deleted_size = 0
        self.failed_count = 0

    def delete_file(self, filepath: Path, backup: bool = False) -> bool:
        """Delete or backup a file."""
        try:
            if not filepath.exists():
                return True

            file_size = filepath.stat().st_size if filepath.is_file() else 0

            if backup and self.backup_dir:
                # Create backup path preserving directory structure
                rel_path = filepath.relative_to(Path.home())
                backup_path = self.backup_dir / rel_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)

                # Handle name conflicts
                if backup_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = backup_path.with_name(f"{backup_path.stem}_{timestamp}{backup_path.suffix}")

                shutil.move(str(filepath), str(backup_path))
            else:
                if filepath.is_dir():
                    filepath.rmdir()
                else:
                    filepath.unlink()

            self.deleted_count += 1
            self.deleted_size += file_size
            return True

        except Exception as e:
            self.failed_count += 1
            return False

    def clean_category(self, files: List[Path], backup: bool = False) -> Tuple[int, int, int]:
        """Clean files in a category. Returns (deleted, failed, size)."""
        self.deleted_count = 0
        self.deleted_size = 0
        self.failed_count = 0

        total = len(files)
        for i, filepath in enumerate(files):
            self.delete_file(filepath, backup)
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i + 1}/{total}", end='\r')

        print(f"  Progress: {total}/{total}  ")
        return self.deleted_count, self.failed_count, self.deleted_size


def confirm(message: str) -> bool:
    """Ask user for confirmation."""
    while True:
        response = input(f"{message} {Colors.YELLOW}[y/N]:{Colors.END} ").strip().lower()
        if response in ('y', 'yes'):
            return True
        if response in ('n', 'no', ''):
            return False


def format_size(size: int) -> str:
    """Format size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def main():
    parser = argparse.ArgumentParser(
        description="Clean up your home directory by finding and removing unwanted files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Categories:
  1. Duplicates    - Files with identical content (keeps newest)
  2. Empty files   - Zero-byte files
  3. Empty dirs    - Directories with no content
  4. Junk files    - .tmp, .log, .DS_Store, .bak, etc.
  5. Large files   - Files over 100MB
  6. Old files     - Not modified in 120+ days

Examples:
  %(prog)s                      # Scan and interactive cleanup
  %(prog)s --backup             # Move to ~/.cleanup_backup instead of delete
  %(prog)s --large-mb 500       # Set large file threshold to 500MB
  %(prog)s --old-days 180       # Set old file threshold to 180 days
        """
    )

    parser.add_argument(
        '--path',
        type=Path,
        default=Path.home(),
        help='Directory to clean (default: home directory)'
    )
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Move files to ~/.cleanup_backup instead of deleting'
    )
    parser.add_argument(
        '--large-mb',
        type=int,
        default=100,
        help='Threshold for large files in MB (default: 100)'
    )
    parser.add_argument(
        '--old-days',
        type=int,
        default=120,
        help='Threshold for old files in days (default: 120)'
    )
    parser.add_argument(
        '--show-all',
        action='store_true',
        help='Show all items (no limit) in category details'
    )

    args = parser.parse_args()

    # Banner
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 70}")
    print(f"               HOME DIRECTORY CLEANUP TOOL")
    print(f"{'=' * 70}{Colors.END}")

    if args.backup:
        backup_dir = Path.home() / '.cleanup_backup'
        print(f"\n{Colors.GREEN}Backup mode enabled:{Colors.END} Files will be moved to {backup_dir}")
    else:
        backup_dir = None
        print(f"\n{Colors.YELLOW}Warning:{Colors.END} Files will be permanently deleted!")

    # Scan
    scanner = CleanupScanner(args.path, args.large_mb, args.old_days)
    scanner.scan()
    scanner.print_summary()

    # Check if anything was found
    total_items = (len(scanner.duplicates) + len(scanner.empty_files) +
                   len(scanner.empty_dirs) + len(scanner.junk_files) +
                   len(scanner.large_files) + len(scanner.old_files))

    if total_items == 0:
        print(f"{Colors.GREEN}Your home directory is clean! Nothing to do.{Colors.END}\n")
        return

    # Interactive menu
    cleaner = Cleaner(backup_dir)
    display_limit = None if args.show_all else 20

    while True:
        print(f"\n{Colors.BOLD}OPTIONS:{Colors.END}")
        print(f"  {Colors.CYAN}[1-6]{Colors.END}  View details for a category")
        print(f"  {Colors.CYAN}[d1-d6]{Colors.END} Delete/backup items in a category")
        print(f"  {Colors.CYAN}[a]{Colors.END}    Delete/backup ALL categories")
        print(f"  {Colors.CYAN}[r]{Colors.END}    Rescan directory")
        print(f"  {Colors.CYAN}[q]{Colors.END}    Quit")

        choice = input(f"\n{Colors.BOLD}Enter choice:{Colors.END} ").strip().lower()

        if choice == 'q':
            print(f"\n{Colors.GREEN}Goodbye!{Colors.END}\n")
            break

        elif choice == 'r':
            scanner = CleanupScanner(args.path, args.large_mb, args.old_days)
            scanner.scan()
            scanner.print_summary()

        elif choice in ['1', '2', '3', '4', '5', '6']:
            scanner.print_category_details(choice, display_limit or 1000)

        elif choice.startswith('d') and choice[1:] in ['1', '2', '3', '4', '5', '6']:
            category = choice[1:]
            files = scanner.get_files_for_category(category)

            if not files:
                print(f"\n{Colors.YELLOW}No items in this category.{Colors.END}")
                continue

            category_names = {
                "1": "duplicate files",
                "2": "empty files",
                "3": "empty directories",
                "4": "junk files",
                "5": "large files",
                "6": "old files"
            }

            action = "move to backup" if args.backup else "permanently delete"
            print(f"\n{Colors.RED}About to {action} {len(files)} {category_names[category]}.{Colors.END}")

            if confirm(f"Are you sure?"):
                if args.backup:
                    backup_dir.mkdir(parents=True, exist_ok=True)

                deleted, failed, size = cleaner.clean_category(files, args.backup)

                print(f"\n{Colors.GREEN}Completed:{Colors.END}")
                print(f"  {'Moved' if args.backup else 'Deleted'}: {deleted} items ({format_size(size)})")
                if failed:
                    print(f"  {Colors.RED}Failed: {failed} items{Colors.END}")

                # Clear the cleaned category
                if category == "1":
                    scanner.duplicates.clear()
                elif category == "2":
                    scanner.empty_files.clear()
                elif category == "3":
                    scanner.empty_dirs.clear()
                elif category == "4":
                    scanner.junk_files.clear()
                elif category == "5":
                    scanner.large_files.clear()
                elif category == "6":
                    scanner.old_files.clear()
            else:
                print(f"\n{Colors.YELLOW}Cancelled.{Colors.END}")

        elif choice == 'a':
            all_files = []
            for cat in ['1', '2', '3', '4', '5', '6']:
                all_files.extend(scanner.get_files_for_category(cat))

            if not all_files:
                print(f"\n{Colors.YELLOW}Nothing to clean.{Colors.END}")
                continue

            action = "move to backup" if args.backup else "permanently delete"
            print(f"\n{Colors.RED}About to {action} {len(all_files)} items from ALL categories.{Colors.END}")
            print(f"{Colors.RED}This includes duplicates, empty files/dirs, junk, large, and old files!{Colors.END}")

            if confirm("Are you ABSOLUTELY sure?"):
                if confirm("Last chance - this cannot be undone. Continue?"):
                    if args.backup:
                        backup_dir.mkdir(parents=True, exist_ok=True)

                    deleted, failed, size = cleaner.clean_category(all_files, args.backup)

                    print(f"\n{Colors.GREEN}Completed:{Colors.END}")
                    print(f"  {'Moved' if args.backup else 'Deleted'}: {deleted} items ({format_size(size)})")
                    if failed:
                        print(f"  {Colors.RED}Failed: {failed} items{Colors.END}")

                    # Clear all categories
                    scanner.duplicates.clear()
                    scanner.empty_files.clear()
                    scanner.empty_dirs.clear()
                    scanner.junk_files.clear()
                    scanner.large_files.clear()
                    scanner.old_files.clear()
                else:
                    print(f"\n{Colors.YELLOW}Cancelled.{Colors.END}")
            else:
                print(f"\n{Colors.YELLOW}Cancelled.{Colors.END}")

        else:
            print(f"\n{Colors.YELLOW}Invalid choice. Try again.{Colors.END}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Cancelled by user.{Colors.END}\n")
        sys.exit(0)
