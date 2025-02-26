#!/usr/bin/env python

from collections import OrderedDict
from io import BytesIO
import struct
import sys

import pytest
from pytest import raises, xfail

from msgpack_sorted import packb, unpackb, Unpacker, Packer, pack


def check(data, use_list=False):
    re = unpackb(packb(data), use_list=use_list, strict_map_key=False)
    assert re == data


def testPack():
    test_data = [
        0,
        1,
        127,
        128,
        255,
        256,
        65535,
        65536,
        4294967295,
        4294967296,
        -1,
        -32,
        -33,
        -128,
        -129,
        -32768,
        -32769,
        -4294967296,
        -4294967297,
        1.0,
        b"",
        b"a",
        b"a" * 31,
        b"a" * 32,
        None,
        True,
        False,
        (),
        ((),),
        ((), None),
        {None: 0},
        (1 << 23),
    ]
    for td in test_data:
        check(td)


def testPackUnicode():
    test_data = ["", "abcd", ["defgh"], "Русский текст"]
    for td in test_data:
        re = unpackb(packb(td), use_list=1, raw=False)
        assert re == td
        packer = Packer()
        data = packer.pack(td)
        re = Unpacker(BytesIO(data), raw=False, use_list=1).unpack()
        assert re == td


def testPackBytes():
    test_data = [b"", b"abcd", (b"defgh",)]
    for td in test_data:
        check(td)


def testPackByteArrays():
    test_data = [bytearray(b""), bytearray(b"abcd"), (bytearray(b"defgh"),)]
    for td in test_data:
        check(td)


def testIgnoreUnicodeErrors():
    re = unpackb(packb(b"abc\xeddef", use_bin_type=False), raw=False, unicode_errors="ignore")
    assert re == "abcdef"


def testStrictUnicodeUnpack():
    packed = packb(b"abc\xeddef", use_bin_type=False)
    with pytest.raises(UnicodeDecodeError):
        unpackb(packed, raw=False, use_list=1)


def testIgnoreErrorsPack():
    re = unpackb(
        packb("abc\uDC80\uDCFFdef", use_bin_type=True, unicode_errors="ignore"),
        raw=False,
        use_list=1,
    )
    assert re == "abcdef"


def testDecodeBinary():
    re = unpackb(packb(b"abc"), use_list=1)
    assert re == b"abc"


def testPackFloat():
    assert packb(1.0, use_single_float=True) == b"\xca" + struct.pack(">f", 1.0)
    assert packb(1.0, use_single_float=False) == b"\xcb" + struct.pack(">d", 1.0)


def testArraySize(sizes=[0, 5, 50, 1000]):
    bio = BytesIO()
    packer = Packer()
    for size in sizes:
        bio.write(packer.pack_array_header(size))
        for i in range(size):
            bio.write(packer.pack(i))

    bio.seek(0)
    unpacker = Unpacker(bio, use_list=1)
    for size in sizes:
        assert unpacker.unpack() == list(range(size))


def test_manualreset(sizes=[0, 5, 50, 1000]):
    packer = Packer(autoreset=False)
    for size in sizes:
        packer.pack_array_header(size)
        for i in range(size):
            packer.pack(i)

    bio = BytesIO(packer.bytes())
    unpacker = Unpacker(bio, use_list=1)
    for size in sizes:
        assert unpacker.unpack() == list(range(size))

    packer.reset()
    assert packer.bytes() == b""


def testMapSize(sizes=[0, 5, 50, 1000]):
    bio = BytesIO()
    packer = Packer()
    for size in sizes:
        bio.write(packer.pack_map_header(size))
        for i in range(size):
            bio.write(packer.pack(i))  # key
            bio.write(packer.pack(i * 2))  # value

    bio.seek(0)
    unpacker = Unpacker(bio, strict_map_key=False)
    for size in sizes:
        assert unpacker.unpack() == {i: i * 2 for i in range(size)}


def test_odict():
    seq = [(b"one", 1), (b"two", 2), (b"three", 3), (b"four", 4)]
    od = OrderedDict(seq)
    assert unpackb(packb(od), use_list=1) == dict(seq)

    def pair_hook(seq):
        return list(seq)

    assert unpackb(packb(od), object_pairs_hook=pair_hook, use_list=1) == seq


def test_pairlist():
    pairlist = [(b"a", 1), (2, b"b"), (b"foo", b"bar")]
    packer = Packer()
    packed = packer.pack_map_pairs(pairlist)
    unpacked = unpackb(packed, object_pairs_hook=list, strict_map_key=False)
    assert pairlist == unpacked


def test_get_buffer():
    packer = Packer(autoreset=0, use_bin_type=True)
    packer.pack([1, 2])
    strm = BytesIO()
    strm.write(packer.getbuffer())
    written = strm.getvalue()

    expected = packb([1, 2], use_bin_type=True)
    assert written == expected


def test_sort_keys(sizes=[3, 31, 127, 1023]):
    for size in sizes:
        keys = range(1, 1000000000, 1000000000 // size)
        map1 = {k: k for k in keys}
        map2 = {k: k for k in reversed(keys)}
        assert packb(map1, sort_keys=False) != packb(map2, sort_keys=False)
        assert packb(map1, sort_keys=True) == packb(map2, sort_keys=True)
