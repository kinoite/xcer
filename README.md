# Xcer Package Manager

*A simple, package manager built from scratch in Python.*

> [!WARNING]
> Xcer is currently in an **alpha stage** of development.

Xcer is a complete package manager ecosystem for Xeronic Linux that is meant to replace the deprecated hoshipkg. It includes a command-line client (`xcli`), a package build tool (`xcbuild`), and a simple repository.

## Features

* **Dependency Resolution:** Automatically resolves and installs dependencies for packages.
* **File Conflict Checking:** Safely checks for file conflicts before installation to prevent overwriting files from other packages.
* **Simple Package Format:** Uses standard, easy-to-understand `.tar.gz` packages.
* **Local Caching:** Caches downloaded packages to save bandwidth and speed up subsequent installations.
* **Full Command Suite:** Implements the essential package management commands:
    * `add`: Install new packages.
    * `del`: Uninstall packages cleanly.
    * `upd`: Update all installed packages.
    * `list`: List all installed packages.
    * `search`: Search for available packages in the repository.

## The Xcer Ecosystem

The project is composed of several components, each with a specific role.

### The Xcer Client (`xcli`) - **Needed**

This is the main command-line tool for managing software on your system. If you just want to use Xcer to install packages, this is the only component you need to install.

### The Build Tool (`xcbuild.py`) - **Optional**

This is a separate script for developers and package maintainers. You only need this if you are willing to help by packaging new software for the Xcer repository.

## Installation

The recommended way to install `xcli` is by building a self-contained binary using `PyInstaller`.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/kinoite/xcer.git
    cd xcer
    ```
    *(Note: Ensure your main script file is named `xcli.py` for the next step).*

2.  **Install Build Dependencies:**
    This will install `PyInstaller` and the libraries `xcli` needs to run.
    ```bash
    python3 -m pip install pyinstaller requests tqdm
    ```

3.  **Build the `xcli` Binary:**
    Run `PyInstaller` from the root of the project directory.
    ```bash
    pyinstaller --name xcli --onefile --clean xcli.py
    ```
    This command creates a single executable file in a new `dist/` directory.

4.  **Install the Binary:**
    Copy the newly created binary to `/usr/bin`, which will make it available as a system-wide command. You will need root privileges for this.
    ```bash
    sudo cp dist/xcli /usr/bin/xcli
    ```

5.  **Create Configuration File:**
    For `xcli` to work, it needs a configuration file at `/etc/xcer.conf`.
    ```bash
    sudo cp xcer.conf.example /etc/xcer.conf
    # You can then edit /etc/xcer.conf if needed.
    ```

## Usage

#### Using `xcli` (For Everyone)

Once installed, you can use `xcli` like any other package manager. Commands that modify the system require root privileges.

* **Search for a package:**
    ```bash
    xcli search openbox
    ```

* **Install a package:**
    ```bash
    sudo xcli add openbox
    ```

* **List installed packages:**
    ```bash
    xcli list
    ```

* **Uninstall a package:**
    ```bash
    sudo xcli del openbox
    ```

#### Packaging with `xcbuild` (For Packagers)

1.  **Prepare Source:** Arrange the program's files in the `source_packages/` directory.
2.  **Build the Package:** Run `xcbuild.py` with the appropriate flags.
    ```bash
    xcbuild openbox --version=3.6.1-12 --depends=imlib2
    ```

## License

This project is licensed under the terms of the **GNU General Public License v3.0**.
