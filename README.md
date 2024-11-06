# Boozook

Tools for extracting and editing Coktel Vision game resources.

## Table of Contents

1. [Features](#features)
2. [Supported Games](#supported-games)
3. [Installation](#installation)
4. [Usage](#usage)
    1. [Interactive Mode](#interactive-mode)
    2. [Non-Interactive Mode](#non-interactive-mode)
    3. [Resource Options](#resource-options)
        - [Texts](#texts)
        - [Graphics](#graphics)
        - [Archives](#archives)
        - [Fonts](#fonts)
5. [Examples](#examples)
6. [Experimental Support](#experimental-support)
    1. [Scripts](#scripts)
7. [Contributions](#contributions)
8. [License](#license)

## Features

- Extract and rebuild game archives
- Extract or inject game texts
- Extract or inject game fonts
- Extract or inject game graphics
- Decompile game scripts (**experimental**)

## Supported Games

- Adi 1
- Adi 2
- Adi 4 (DEV6)
- Adi 5 (DEV7)
- Adibou 1
- Adibou 2 (DEV6)
- Adibou 3 (DEV7)
- Adibou présente series (DEV7)
- Adiboud'chou series (DEV7)
- Asterix Operation Getafix
- A.G.E
- Bargon Attack
- E.S.S. Mega
- Inca
- Inca 2
- Galactic Empire
- Geisha
- Goblins 1
- Gobliins 2
- Gobliiins 3
- Woodruff
- Croustibat
- Fascination
- Paris Paker 1990
- Playtoons series
- Le pays des pierres Magiques
- Ween: The Prophecy
- Once Upon series
- Urban Runner

## Installation

You can download the latest version of the program below. The program is a single executable file with no additional dependencies required.

**Linux:** [Download for Linux](https://nightly.link/adventurebrew/boozook/workflows/main/organize/boozook-Linux.zip)

**Windows:** [Download for Windows](https://nightly.link/adventurebrew/boozook/workflows/main/organize/boozook-Windows.zip)

**macOS:** [Download for macOS](https://nightly.link/adventurebrew/boozook/workflows/main/organize/boozook-macOS.zip)

**Note:** If the download links do not work, please check the repository for the latest versions or report an issue.

## Usage

The tool can be used in both interactive and non-interactive modes. The game directory is the folder where your game files are located. If you don't specify it, the current working directory (the directory the program was run from) will be used.

### Interactive Mode

Run the tool without any arguments to enter interactive mode:

```sh
boozook [GAME_PATH]
```

**Tip:** You can drag and drop the game directory onto the executable file to start in interactive mode easily.

You will be prompted to select actions and options through a series of menus.

### Non-Interactive Mode (Advanced Usage)

This mode is considered advanced and is recommended for users familiar with command-line interfaces and scripting.

Specify command-line arguments to run the tool non-interactively, so it can be used in scripts.

### Resource Options

The CLI flags specify which resources are selected for extracting. For example, the command:

```sh
boozook --fonts --archive
```

extracts fonts and archives and ignores other resources.

For a comprehensive list of all available options and their use cases, refer to the documentation or use the help command:

```sh
boozook --help
```

#### Texts

Texts are exported from `.cat` and `.tot` files into `.csv` files.

- `-t, --texts`: Extract or inject texts.

  ```sh
  boozook /path/to/game/directory --texts
  ```

- `-i, --allowed`: Allow only specific patterns to be modified.

  ```sh
  boozook /path/to/game/directory --texts --allowed "*.ISR" "*.CAT"
  ```

- `-k, --keys`: Replace text by keyboard key position (custom encoding used for the official Hebrew translation of some games).

  ```sh
  boozook /path/to/game/directory --texts --keys
  ```

#### Graphics

Graphics are exported from `.ext` and `.tot` files into `.png` files.

- `-g, --graphics`: Extract or inject graphics.

  ```sh
  boozook /path/to/game/directory --graphics
  ```

#### Archives

Raw files are extracted from archives, usually STK, ITK, LTK, JTK, and can be configured by the patterns flag.

- `-a, --archive`: Extract or rebuild game archives.

  ```sh
  boozook /path/to/game/directory --archive
  ```

- `-p, --patterns`: File patterns to consider as archives to extract.

  ```sh
  boozook /path/to/game/directory --archive --patterns "*.ITK" "*.STK"
  ```

#### Fonts

Fonts are extracted from `.let` files to `.png` files with the characters displayed on a 16x16 grid.

- `-f, --fonts`: Extract or inject fonts.

  ```sh
  boozook /path/to/game/directory --fonts
  ```

### Rebuild

The same command used to extract resources can also be used to rebuild them by adding the `-r` flag.

### Examples

**Example Use Case**

Suppose you want to translate a game. Here are the steps for both interactive and non-interactive modes:

#### Interactive Mode

1. **Extract Resources**:
   - Drag and drop the game directory onto the executable file to start in interactive mode.
   - Select "Extract" from the menu.
   - Select "Fonts" and "Texts" by pressing the space bar.
   - Press "a" to display the advanced options menu, if needed.
   - Press "Enter" to start the extraction process.

   CSV files will be created with the texts and PNG files with the font, which you will need to edit.

2. **Edit the Font**:
   - Edit the PNG files of the font as needed.

3. **Edit the Texts**:
   - Edit the texts in the CSV files as needed.

4. **Inject Resources**:
   - Drag and drop the game directory onto the executable file again to start in interactive mode.
   - Select "Inject" from the menu.
   - Select "Fonts" and "Texts" by pressing the space bar and then "Enter".

   Copy the created files over into the original game directory to apply the changes.

#### Non-Interactive Mode (Advanced Usage)

This is the same example, executed in non-interactive mode:

1. **Extract Resources**:
   ```sh
   boozook /path/to/game/directory --texts --fonts
   ```

   CSV files will be created with the texts and PNG files with the font, which you will need to edit.

2. **Edit the Font**:
   - Edit the PNG files of the font as needed.

3. **Edit the Texts**:
   - Edit the texts in the CSV files as needed.

4. **Inject Resources**:
   ```sh
   boozook /path/to/game/directory --texts --fonts -r
   ```

   Copy the created files over into the original game directory to apply the changes.

### Experimental Support (Advanced Usage)

Additional options for the program are available with this flag. 

**Warning:** These features may have bugs, incomplete implementations, and potential changes in behavior.

- `--experimental`: Enable experimental features including script decompilation.

For a comprehensive list of all available options and their use cases, including experimental options, refer to the documentation or use the help command along with the `--experimental` modifier:

```sh
boozook --experimental --help
```

**Tip:** You can also run experimental features in interactive mode for easier discovery.

```sh
boozook --experimental
```

### Scripts

- `-s, --scripts`: Decompile game scripts.

  ```sh
  boozook /path/to/game/directory --experimental --scripts
  ```

  You can also specify specific patterns for scripts to decompile:

  ```sh
  boozook /path/to/game/directory --experimental --scripts INTRO*.TOT
  ```

- `-l, --lang`: Language to focus on message hints in decompiled scripts.

  ```sh
  boozook /path/to/game/directory --experimental --scripts *.TOT --lang en
  ```

- `-e, --exported`: Only decompile exported functions (similar to `degob` of ScummVM Tools), rather than attempt complete decompilation.

  ```sh
  boozook /path/to/game/directory --experimental --scripts *.TOT --exported
  ```

- Note: Text options are also considered for scripts.

  ```sh
  boozook /path/to/game/directory --experimental --scripts *.TOT --lang he --keys
  ```

### Contributions

Feel free to submit issues, fork the repository, and send pull requests. Contributions are always welcome!

#### Community Contributions

This tool has already been used to translate several games successfully. Here are some examples:
- **Croustibat**: Translated into German.
- **Gobliins 2**: Translated into Hebrew.
- **Ween: The Prophecy**: Translated into Hebrew.

We encourage you to share your user-created mods, translations, and improvements in the [issues section](https://github.com/adventurebrew/boozook/issues) of this repository to inspire and collaborate with other users.
Please feel free to let us know and expand the above list.

**Important:** While we encourage the sharing of your mods, please do not share the original game files.

#### Reporting Bugs and Requesting Improvements

If you encounter any bugs or use cases that aren't met by the current capabilities of this program, please report them in the [issues section](https://github.com/adventurebrew/boozook/issues) of this repository. When reporting a bug, include detailed information such as the steps to reproduce the issue and any error messages received. If you have suggestions for improvements based on specific tasks or workflows you would like to accomplish, feel free to share those as well.

#### Development

To develop or contribute to this project, you can clone the repository and set it up using Python >= 3.12 and [Poetry](https://python-poetry.org/) (a tool for dependency management and packaging in Python).

See "Running Development Version" below for detailed instructions.

### Running Development Version

1. **Clone the Repository**:
   ```sh
   git clone https://github.com/adventurebrew/boozook.git
   ```

2. **Navigate to the Project Directory**:
   ```sh
   cd boozook
   ```

3. **Ensure you have Python >= 3.12 installed**:
   You can check your Python version by running:
   ```sh
   python --version
   ```

4. **Install Dependencies**:
   ```sh
   poetry install
   ```

5. **Activate poetry shell**:
   ```sh
   poetry shell
   ```

Now you have `boozook` program available to execute from your shell, with ability to modify the program locally.

#### Further Reading and Resources

For more information about the technical details of the games supported by Boozook, please refer to the [ScummVM wiki page on the Gob engine](https://wiki.scummvm.org/index.php/Gob).

## License

This project is licensed under the GPL-3.0 License, which allows you to use, modify, and distribute the software, ensuring that any derivative works remain open and licensed under GPL-3.0. See the `LICENSE` file for more details.

**Disclaimer:** This project is a fan-made initiative and is not affiliated with, endorsed by, or associated with the copyright holders of the original Coktel Vision games. All trademarks and registered trademarks are the property of their respective owners.
