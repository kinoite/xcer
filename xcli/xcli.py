#!/usr/bin/env python

# xcli.py -- the core of xcli

import os
import sys
import tarfile
import requests
from pathlib import Path
import configparser
import shutil
from tqdm import tqdm
import traceback

def load_config():
    """
    Loads configuration by searching in user, system, and local paths.
    """
    user_config_path = Path.home() / '.config' / 'xology' / 'xcer.conf'
    system_config_path = Path('/etc/xcer.conf')
    local_config_path = Path('xcer.conf')

    config_path_to_use = None
    if user_config_path.exists():
        config_path_to_use = user_config_path
    elif system_config_path.exists():
        config_path_to_use = system_config_path
    elif local_config_path.exists():
        config_path_to_use = local_config_path
    else:
        print(f"❌ Error: Config file not found.")
        print("Please create one at ~/.config/xology/xcer.conf, /etc/xcer.conf, or ./xcer.conf")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path_to_use)

    return {
        'RootDir': Path(config['options']['RootDir']),
        'DBPath': Path(config['options']['DBPath']),
        'CacheDir': Path.home() / '.cache' / 'xcer'
    }

def fetch_package_index():
    """Downloads the main package index file from the remote repository."""
    REMOTE_REPO_URL = "http://192.168.8.50:8000"
    PACKAGE_INDEX_URL = f"{REMOTE_REPO_URL}/packages.json"
    try:
        response = requests.get(PACKAGE_INDEX_URL)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error fetching package index: {e}")
        return None
    except requests.exceptions.JSONDecodeError as e:
        print(f"❌ Error parsing package index. Is packages.json valid?: {e}")
        return None

def resolve_dependencies(package_names, index):
    """Recursively finds all dependencies for a list of packages."""
    to_install = set()
    resolved = set()
    def _resolve(name):
        if name in resolved: return
        if name not in index: raise ValueError(f"Dependency '{name}' not found.")
        for dep in index[name].get("dependencies", []): _resolve(dep)
        to_install.add(name)
        resolved.add(name)
    for name in package_names: _resolve(name)
    return list(to_install)

def download_and_cache_package(package_name, package_info, cache_dir):
    """Downloads a package if not in cache. Returns the path to the cached file."""
    package_url = package_info['url']
    file_name = package_url.split('/')[-1]
    cached_file_path = cache_dir / file_name
    if cached_file_path.exists():
        print(f"-> Using cached package for {package_name}.")
        return cached_file_path

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        with requests.get(package_url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc=f"Downloading {package_name}") as pbar:
                with open(cached_file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
        return cached_file_path
    except requests.RequestException as e:
        print(f"\n❌ Error downloading {package_name}: {e}")
        return None

def check_permissions(root_dir):
    """Checks if we have write permissions to the root directory."""
    if os.access(root_dir, os.W_OK): return True
    print(f"❌ Error: No write permissions for '{root_dir}'. Please run with sudo or doas.")
    return False

def get_installed_packages(db_path):
    """Returns a dict of installed packages {name: version}."""
    installed = {}
    if not db_path.exists(): return installed
    for entry in db_path.glob('*-*'):
        if entry.is_dir():
            parts = entry.name.rsplit('-', 1)
            if len(parts) == 2: installed[parts[0]] = parts[1]
    return installed

def extract_and_register(archive_path, config):
    """
    Extracts a .tar.gz package, ensuring file permissions are correctly set.
    """
    root_dir = config['RootDir']
    db_path = config['DBPath']

    try:
        db_path.mkdir(parents=True, exist_ok=True)
        pkg_info_data = None

        with tarfile.open(archive_path, "r:gz") as th:
            for member in tqdm(th, desc=f"Extracting  {archive_path.name.replace('.tar.gz', '')}", unit=" files", leave=False):
                if member.name == ".PKGINFO":
                    pkginfo_file_obj = th.extractfile(member)
                    if pkginfo_file_obj:
                        pkg_info_data = pkginfo_file_obj.read().decode('utf-8')
                elif member.name != ".":

                    th.extract(member, path=root_dir)

        if pkg_info_data:
            name = [line for line in pkg_info_data.split('\n') if 'name =' in line][0].split('=')[1].strip()
            version = [line for line in pkg_info_data.split('\n') if 'version =' in line][0].split('=')[1].strip()
            pkg_db_entry = db_path / f"{name}-{version}"
            pkg_db_entry.mkdir(exist_ok=True)
            with open(pkg_db_entry / 'PKGINFO', 'w') as f:
                f.write(pkg_info_data)
        else:
            raise RuntimeError(".PKGINFO not found in package!")

    except Exception as e:
        print(f"\n❌ Error during extraction/registration: {e}")
        raise

def check_for_conflicts(packages_to_install, index, config):
    """
    Checks if files from packages_to_install conflict with any already
    installed packages. This is a crucial safety check.
    """
    print("-> Checking for file conflicts...")
    db_path = config['DBPath']
    cache_dir = config['CacheDir']

    installed_files = set()
    installed_packages = get_installed_packages(db_path)
    for name, version in installed_packages.items():

        if name in packages_to_install:
            continue

        pkg_db_entry = db_path / f"{name}-{version}"
        with open(pkg_db_entry / 'PKGINFO', 'r') as f:
            for line in f:
                if line.startswith('file ='):
                    installed_files.add(line.split('=', 1)[1].strip())

    for name in packages_to_install:
        package_info = index[name]
        file_name = package_info['url'].split('/')[-1]
        cached_file_path = cache_dir / file_name

        if not cached_file_path.exists():
            print(f"❌ Error: Package {name} not found in cache for conflict check.")
            return False 

        with tarfile.open(cached_file_path, "r:gz") as th:
            for member in th:
                if member.name.startswith('file ='): 
                    new_file_path = member.name.split('=', 1)[1].strip()
                    if new_file_path in installed_files:
                        print(f"❌ Conflict Error: File '{new_file_path}' from package '{name}' is already owned by another package.")
                        return False 

    print("-> No conflicts found.")
    return True 

def add(package_names, config):
    """
    Adds one or more packages to the system, now with conflict checking.
    """
    if not check_permissions(config['RootDir']): sys.exit(1)

    print(":: Synchronizing package databases...")
    index = fetch_package_index()
    if not index: return

    print("-> Resolving dependencies...")
    try: all_packages = resolve_dependencies(package_names, index)
    except ValueError as e: print(f"❌ Error: {e}"); return

    installed_packages = get_installed_packages(config['DBPath'])
    packages_to_install = [p for p in all_packages if p not in installed_packages or installed_packages[p] != index[p]['version']]

    if not packages_to_install:
        print("-> Nothing to do. All packages are up to date.")
        return

    print("\nPackages to add:")
    for p in packages_to_install: print(f"  {p}-{index[p]['version']}")

    print()
    if input(":: Proceed with installation? [Y/n] ").lower() not in ['y', 'yes', '']:
        print("-> Aborting."); return

    print("\n:: Downloading packages...")
    downloaded_archives = []
    for name in packages_to_install:
        archive_path = download_and_cache_package(name, index[name], config['CacheDir'])
        if archive_path:
            downloaded_archives.append((name, archive_path))
        else:
            print(f"-> Failed to download {name}. Aborting installation.")
            return

    if not check_for_conflicts(packages_to_install, index, config):
        print("-> Installation aborted due to file conflicts.")
        return

    print("\n:: Installing packages...")
    for name, archive_path in downloaded_archives:

        if name in installed_packages:
            del_pkg(name, config, quiet=True)

        extract_and_register(archive_path, config)

    print("\n-> Installation complete.")

def del_pkg(package_name, config, quiet=False):
    """Deletes a package from the system."""
    if not quiet and not check_permissions(config['RootDir']): sys.exit(1)
    pkg_db_entry = next(config['DBPath'].glob(f'{package_name}-*'), None)
    if not pkg_db_entry:
        if not quiet: print(f"-> Package '{package_name}' is not installed.")
        return
    if not quiet: print(f":: Removing package {pkg_db_entry.name}...")
    with open(pkg_db_entry / 'PKGINFO', 'r') as f:
        files = [line.split('=')[1].strip() for line in f if line.startswith('file =')]
    for file_path in tqdm(sorted(files, reverse=True), desc="Removing files", unit=" file", leave=False):
        try: (config['RootDir'] / file_path).unlink()
        except FileNotFoundError: pass
    for file_path in sorted(files, reverse=True):
        try:
            dir_path = (config['RootDir'] / file_path).parent
            if not any(dir_path.iterdir()): dir_path.rmdir()
        except (FileNotFoundError, OSError): pass
    shutil.rmtree(pkg_db_entry)
    if not quiet: print(f"-> Uninstalled {pkg_db_entry.name}.")

def update_system(config):
    """Checks all installed packages for updates and installs them."""
    print(":: Starting system upgrade...")
    index = fetch_package_index()
    if not index: return
    installed = get_installed_packages(config['DBPath'])
    to_update = [name for name, ver in installed.items() if name in index and index[name]['version'] != ver]
    if not to_update: print("-> There is nothing to do."); return
    print("-> The following packages will be upgraded:")
    for name in to_update: print(f"  {name} {installed[name]} -> {index[name]['version']}")
    add(to_update, config)

def list_installed(config):
    """Lists all locally installed packages."""
    installed = get_installed_packages(config['DBPath'])
    if not installed: print("-> No packages installed."); return
    for name, version in sorted(installed.items()): print(f"{name} {version}")

def search_remote(search_terms, config):
    """Searches for packages in the remote index."""
    if not search_terms: print("Usage: xcli search <term...>"); return
    print(":: Searching remote repository...")
    index = fetch_package_index()
    if not index: return
    found = [info for name, info in index.items() if any(t.lower() in name.lower() for t in search_terms)]
    for info in sorted(found, key=lambda i: i['name']): print(f"{info['name']} {info['version']}")
    if not found: print("-> No packages found.")

def main():
    """Main command-line interface logic with enhanced error reporting."""
    try:
        print("DEBUG: xcli script execution started.")
        config = load_config()
        args = sys.argv[1:]
        if not args:
            print("Usage: xcli <command> [args...]\nCommands: add, del, upd, list, search")
            sys.exit(1)
        command, cmd_args = args[0], args[1:]
        print(f"DEBUG: Command is '{command}', arguments are {cmd_args}")
        commands = {
            'add': lambda p,c: add(p,c),
            'del': lambda p,c: [del_pkg(n,c) for n in p],
            'upd': lambda p,c: update_system(c),
            'list': lambda p,c: list_installed(c),
            'search': lambda p,c: search_remote(p, c)
        }
        if command in commands:
            if command in ['add', 'del', 'search'] and not cmd_args:
                print(f"Usage: xcli {command} <package...>"); sys.exit(1)
            commands[command](cmd_args, config)
        else:
            print(f"Unknown command: {command}"); sys.exit(1)
    except KeyboardInterrupt:
        print("\n-> Operation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        import traceback
        print("\n‼️ An unexpected and hidden error occurred! ‼️")
        print("This is the detailed error report (traceback):")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
