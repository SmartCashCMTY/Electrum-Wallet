Windows Binary Builds
=====================

These scripts can be used for cross-compilation of Windows Electrum executables from Linux/Wine.
Produced binaries are deterministic, so you should be able to generate binaries that match the official releases. 


Usage:


1. Install the following dependencies:

 - dirmngr
 - gpg
 - 7Zip
 - Wine (>= v2)

 $ sudo apt-get install dirmngr gnupg2 p7zip-full

 -----------Install Wine 4.0-------- 

 Standard apt install with 3.0 and doesn't include mono or gecko. This install will ask to install mono and gecko automatically on first build.
 
 $ sudo dpkg --add-architecture i386

 $ wget -nc https://dl.winehq.org/wine-builds/winehq.key

 $ sudo apt-key add winehq.key

 (Choose one)
 
 $ sudo apt-add-repository 'deb https://dl.winehq.org/wine-builds/ubuntu/ bionic main' [Ubuntu 18.04 & Linux Mint 19.x]

 $ sudo apt-add-repository 'deb https://dl.winehq.org/wine-builds/ubuntu/ xenial main' [Ubuntu 16.04 & Linux Mint 18.x]

 $ sudo apt-add-repository 'deb https://dl.winehq.org/wine-builds/ubuntu/ cosmic main' [Ubuntu 18.10]

 $ sudo apt-get update
 $ sudo apt-get install --install-recommends winehq-stable

 $ wine --version
   wine-4.0

2. Make sure `/opt` is writable by the current user.  
 $ sudo chown -R $USER:$USER /opt

3. Run `build.sh`.

4. The generated binaries are in `./dist`.
