#!/bin/bash
# Secure File Delete Launcher

cd ~

# Function to clean drag & drop paths
clean_path() {
    local p="$1"
    # Remove surrounding single quotes
    p="${p#\'}"
    p="${p%\'}"
    # Remove backslash escapes (from drag & drop)
    p=$(printf '%s' "$p" | sed 's/\\//g')
    # Remove leading/trailing whitespace
    p=$(printf '%s' "$p" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    printf '%s' "$p"
}

while true; do
    clear
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║           SECURE FILE DELETE TOOL                          ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""
    echo "This tool will permanently delete files so they cannot be recovered."
    echo ""
    echo "Options:"
    echo "  1) Delete a specific file"
    echo "  2) Delete multiple files"
    echo "  3) Delete a folder (recursive)"
    echo "  4) Delete multiple folders"
    echo "  5) Exit"
    echo ""
    read -p "Choose an option (1-5): " choice

    case $choice in
        1)
            echo ""
            read -r -p "Enter file path (or drag & drop file here): " filepath
            filepath=$(clean_path "$filepath")
            echo ""
            read -p "Number of passes (3=quick, 7=standard, 35=paranoid) [7]: " passes
            passes=${passes:-7}
            python3 ~/Desktop/secure_delete.py --passes "$passes" "$filepath"
            ;;
        2)
            echo ""
            echo "Enter file paths (one per line, empty line to finish):"
            files=()
            while IFS= read -r line; do
                [[ -z "$line" ]] && break
                line=$(clean_path "$line")
                [[ -n "$line" ]] && files+=("$line")
            done
            if [ ${#files[@]} -gt 0 ]; then
                read -p "Number of passes [7]: " passes
                passes=${passes:-7}
                python3 ~/Desktop/secure_delete.py --passes "$passes" "${files[@]}"
            fi
            ;;
        3)
            echo ""
            read -r -p "Enter folder path (or drag & drop folder here): " folderpath
            folderpath=$(clean_path "$folderpath")
            echo ""
            read -p "Number of passes [7]: " passes
            passes=${passes:-7}
            python3 ~/Desktop/secure_delete.py -r --passes "$passes" "$folderpath"
            ;;
        4)
            echo ""
            echo "Enter folder paths (one per line, empty line to finish):"
            folders=()
            while IFS= read -r line; do
                [[ -z "$line" ]] && break
                line=$(clean_path "$line")
                [[ -n "$line" ]] && folders+=("$line")
            done
            if [ ${#folders[@]} -gt 0 ]; then
                read -p "Number of passes [7]: " passes
                passes=${passes:-7}
                for folder in "${folders[@]}"; do
                    python3 ~/Desktop/secure_delete.py -r --passes "$passes" "$folder"
                done
            fi
            ;;
        5)
            echo "Goodbye."
            exit 0
            ;;
        *)
            echo "Invalid option."
            ;;
    esac

    echo ""
    echo "Done! Press any key to return to the menu, or Q to quit."
    read -n 1 -s key
    if [[ "$key" == "q" || "$key" == "Q" ]]; then
        exit 0
    fi
done
