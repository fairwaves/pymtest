# pymtest - Python Manufacturing Testing framework

Pymtest is a flexible framework for running post-manufacturing tests of your hardware. It allows you to write arbitrary tests, combine them into test suites, execute them in a GUI or console and store results for later analysis. Test suites are written in YAML and have support for variable substitution and looping making them very flexible.

Pymtes was originally developed to test Fairwaves UmSITEs and UmTRXs during manufacturing and later extended to support OpenCellular base stations. After several iterations of generalization, it became generic enough to support virtually any hardware manufacturing testing.

# Vision

***Open-source is a way to jointly save time for everyone.***

Everyone manufacturing hardware in more than a handful pieces faces the need of automated testing for the manufactured devices. Right now everyone writes their own suite from scratch, sometimes several times which results in significant industry effort spent on reimplementing this wheel instead of improving the actual hardware.

Even in such a specific industry as Software Defined Radio there have been no shared tests for the hardware.

We invite companies manufacturing hardware to contribute to the Pymtest core test framework, as well as contribute test vectors for various types of hardware.

# Currently available test vectors

* GSM BTS tests against R&S CMD57 (contributed by [Fairwaves](https://fairwaves.co))

# Documentation, contributions and questions

Documentation is largely missing for Pymtest as the project evolved from the internal Fairwaves project. We plan to gradually improve this situation, but we strongly encourage everyone to contribute to the documentation as well.

If you have any questions or code to contribute - please use Github Issues and Pull Requests.

# Dependencies

- python3-ecdsa
- python3-paramiko (*)
- python3-pyqt5
- python3-serial
- python3-yaml

(*) For Ubuntu 14.04 install Paramiko manually from the `packages/` subdirectory: `sudo dpkg -i packages/python3-paramiko_1.15.1-1fairwaves1_all.deb`

# Credits

* [Fairwaves, Inc](https://fairwaves.co), and especially [Sergey Kostanbaev](https://github.com/sergforce) and [Alexander Chemeris](https://github.com/chemeris), the original authors of pymtest.

# License

Pymtest is released under the MIT license - a permissive free software license.
