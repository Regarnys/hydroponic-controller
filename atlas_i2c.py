#!/usr/bin/env python3
"""
AtlasI2C driver for Atlas Scientific sensors.
This module provides an interface for communicating with sensors over I2C.
"""

import io
import sys
import fcntl
import time
import copy

class AtlasI2C:
    LONG_TIMEOUT = 1.5
    SHORT_TIMEOUT = 0.3
    DEFAULT_BUS = 1
    DEFAULT_ADDRESS = 98
    LONG_TIMEOUT_COMMANDS = ("R", "CAL")
    SLEEP_COMMANDS = ("SLEEP",)

    def __init__(self, address=None, moduletype="", name="", bus=None):
        self._address = address or self.DEFAULT_ADDRESS
        self.bus = bus or self.DEFAULT_BUS
        self._long_timeout = self.LONG_TIMEOUT
        self._short_timeout = self.SHORT_TIMEOUT
        self.file_read = io.open("/dev/i2c-{}".format(self.bus), mode="rb", buffering=0)
        self.file_write = io.open("/dev/i2c-{}".format(self.bus), mode="wb", buffering=0)
        self.set_i2c_address(self._address)
        self._name = name
        self._module = moduletype

    @property
    def long_timeout(self):
        return self._long_timeout

    @property
    def short_timeout(self):
        return self._short_timeout

    @property
    def name(self):
        return self._name

    @property
    def address(self):
        return self._address

    @property
    def moduletype(self):
        return self._module

    def set_i2c_address(self, addr):
        I2C_SLAVE = 0x703
        fcntl.ioctl(self.file_read, I2C_SLAVE, addr)
        fcntl.ioctl(self.file_write, I2C_SLAVE, addr)
        self._address = addr

    def write(self, cmd):
        cmd += "\00"
        self.file_write.write(cmd.encode('latin-1'))

    def handle_raspi_glitch(self, response):
        if self.app_using_python_two():
            return list(map(lambda x: chr(ord(x) & ~0x80), list(response)))
        else:
            return list(map(lambda x: chr(x & ~0x80), list(response)))

    def app_using_python_two(self):
        return sys.version_info[0] < 3

    def get_response(self, raw_data):
        if self.app_using_python_two():
            response = [i for i in raw_data if i != '\x00']
        else:
            response = raw_data
        return response

    def response_valid(self, response):
        valid = True
        error_code = None
        if len(response) > 0:
            if self.app_using_python_two():
                error_code = str(ord(response[0]))
            else:
                error_code = str(response[0])
            if error_code != '1':
                valid = False
        return valid, error_code

    def get_device_info(self):
        if self._name == "":
            return "{} {}".format(self._module, self.address)
        else:
            return "{} {} {}".format(self._module, self.address, self._name)

    def read(self, num_of_bytes=31):
        raw_data = self.file_read.read(num_of_bytes)
        response = self.get_response(raw_data=raw_data)
        is_valid, error_code = self.response_valid(response=response)
        if is_valid:
            char_list = self.handle_raspi_glitch(response[1:])
            result = "Success " + self.get_device_info() + ": " + ''.join(char_list)
        else:
            result = "Error " + self.get_device_info() + ": " + error_code
        return result

    def get_command_timeout(self, command):
        timeout = None
        if command.upper().startswith(self.LONG_TIMEOUT_COMMANDS):
            timeout = self._long_timeout
        elif not command.upper().startswith(self.SLEEP_COMMANDS):
            timeout = self.short_timeout
        return timeout

    def query(self, command):
        self.write(command)
        current_timeout = self.get_command_timeout(command=command)
        if not current_timeout:
            return "sleep mode"
        else:
            time.sleep(current_timeout)
            return self.read()

    def close(self):
        self.file_read.close()
        self.file_write.close()

    def list_i2c_devices(self):
        prev_addr = copy.deepcopy(self._address)
        i2c_devices = []
        for i in range(0, 128):
            try:
                self.set_i2c_address(i)
                self.read(1)
                i2c_devices.append(i)
            except IOError:
                pass
        self.set_i2c_address(prev_addr)
        return i2c_devices

