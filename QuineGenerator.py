#!/usr/bin/env python3

import Util
import DynamicOP

import re
import os
import sys
import time
import ctypes
import signal
import binascii
import threading

################################

# Give prefixLen and suffixLen, return a list of LZ77 codes
def GetCodes(prefixLen, suffixLen):
    assert prefixLen>0 and prefixLen<32768-5;
    assert suffixLen<32768;

    codes, newPrefix=_solvePrefix(Util.Element("PH", prefixLen, 0));
    assert len(newPrefix)==15;

    tmp=Util.Code("RAW", newPrefix, Util.Element("PH", 5, -1));
    tmp.attr=(*tmp.attr[:-1], tmp.ToElement());
    codes.append(tmp);
    codes.append(Util.Code("OP", 20, 20, 5));
    codes.append(Util.Code("RAW", codes[-1].ToElement(), Util.Element("RAW", 20), codes[-1].ToElement(), Util.Element("RAW", 20)));
    codes.append(Util.Code("OP", 20, 20, 5));

    codes+=_solveSuffix(Util.Element("PH", suffixLen, 1));
    return codes;

# Use LZ77 codes to generate binary data
def Codes2Binary(codes, prefix : bytes, suffix : bytes) -> bytes:
    codes[-1].isFinal=True;
    return b''.join(c.ToBinary({ 0 : prefix, 1 : suffix }) for c in codes);

def _solvePrefix(prefix : Util.Element):
    assert len(prefix)>0;
    if len(prefix)==15:
        return [], prefix;

    l=len(prefix)+5;
    l=l+(128-l%128)%128//5*5;
    assert l%128==0 or l%128>128-5;

    codes=[Util.Code("RAW") for _ in range(len(prefix)+5, l, 5)];
    tmp=Util.Code("RAW", prefix,
        *[c.ToElement() for c in codes],
        Util.Element("PH", 5, None));
    tmp.attr=(*tmp.attr[:-1], tmp.ToElement());
    codes+=[tmp];

    if l<=128:
        codes.append(Util.Code("OP", l, l, 15));
        return codes, codes[-1].ToElement();

    newPrefixLen=0;
    newPrefix=[];
    for i in range(0, l, 128):
        codes.append(Util.Code("OP", l, min(l-i, 128), 19));
        newPrefixLen+=19;
        newPrefix.append(codes[-1]);

    tmp, newPrefix=_solvePrefix(Util.Element("PH", newPrefixLen, newPrefix));
    return codes+tmp, newPrefix;

def _solveSuffix(suffix : Util.Element):
    rawOutLen=len(suffix);
    remLens=[];
    i=0;
    bitLen=DynamicOP.SearchMin(128);
    while i<rawOutLen:
        rawOutLen+=bitLen;
        l=min(rawOutLen-i, 128);
        remLens.append(l);
        i+=l;

    codes=[];
    for l in remLens[::-1]:
        codes.append(Util.Code("OP", rawOutLen, l, bitLen));
    codes.append(Util.Code("RAW", *[x.ToElement() for x in codes[::-1]], suffix));

    codes+=[
        Util.Code("OP", 20, 20, 5),
        Util.Code("RAW"),
        Util.Code("RAW"),
    ];
    codes.append(Util.Code("RAW", codes[-1].ToElement(), codes[-2].ToElement(), codes[-3].ToElement(), codes[-4].ToElement()));
    return codes[::-1];

################################

def QuineGenerate(fileName, includeFilePath):
    exData=open(includeFilePath, "rb").read();
    exFileName=os.path.basename(includeFilePath).encode("utf-8");
    targetCRC32=0x12345678;
    fileName=fileName.encode("utf-8");

    # lxEx, dataEx, lf, data, cdEx, cd, ecd

    lfEx=Util.LocalFile(
        crc32=binascii.crc32(exData),
        compressedSize=len(exData),
        uncompressedSize=len(exData),
        fileNameLength=len(exFileName),
        fileName=exFileName);
    cdEx=Util.CD(
        crc32=lfEx.crc32,
        compressedSize=len(exData),
        uncompressedSize=len(exData),
        fileNameLength=len(exFileName),
        relativeOffset=0,
        fileName=exFileName);

    lf=Util.LocalFile(
        compression=8,
        crc32=targetCRC32,
        compressedSize=None,    # ???
        uncompressedSize=None,  # ???
        fileNameLength=len(fileName),
        fileName=fileName);
    cd=Util.CD(
        compression=8,
        crc32=targetCRC32,
        compressedSize=None,    # ???
        uncompressedSize=None,  # ???
        fileNameLength=len(fileName),
        relativeOffset=lfEx.PackSize()+len(exData),
        fileName=fileName);

    ecd=Util.ECD(
        numEntriesDisk=2,
        numEntries=2,
        sizeCD=cdEx.PackSize(),
        offsetCD=None,          # ???
        sizeComment=4,
        comment=b'0'*4);

    prefixLen=lfEx.PackSize()+len(exData)+lf.PackSize();
    suffixLen=cdEx.PackSize()+cd.PackSize()+ecd.PackSize();
    codes=GetCodes(prefixLen, suffixLen);
    codesLen=sum(len(c) for c in codes);

    lf.compressedSize=cd.compressedSize=codesLen;
    lf.uncompressedSize=cd.uncompressedSize=prefixLen+codesLen+suffixLen;
    ecd.offsetCD=prefixLen+codesLen;

    prefix=lfEx.Pack()+exData+lf.Pack();
    suffix=cdEx.Pack()+cd.Pack()+ecd.Pack();
    data=Codes2Binary(codes, prefix, suffix);
    data=prefix+data+suffix;

    data=_findCrcMulti(data, targetCRC32);
    open(fileName.decode("utf-8"), "wb").write(data);

def _findCrcOne(data, target, poses, L, R):
    handle=ctypes.CDLL("./libSearchCRC.so");
    handle.SearchCRC.argtypes=[ctypes.c_char_p, ctypes.c_int,
        ctypes.c_int*len(poses), ctypes.c_int,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32];
    handle.SearchCRC.restype=ctypes.c_uint32;

    _findCrcOne.finishedSize=0;
    startTime=time.time();
    step=1<<23;
    for LL in range(L, R, step):
        if hasattr(_findCrcOne, "finalAns"):
            break;
        RR=min(R, LL+step);
        ans=handle.SearchCRC(ctypes.create_string_buffer(data), len(data),
            (ctypes.c_int*len(poses))(*poses), len(poses),
            LL, RR & 0xFFFFFFFF, target);
        if ans:
            _findCrcOne.finalAns=ans;

        # DEBUG Output
        _findCrcOne.finishedSize+=RR-LL;
        usedTime=time.time()-startTime;
        print("# Finished: {:.2f}%; Need {:.2f}s".format(
                100*_findCrcOne.finishedSize/(1<<32),
                usedTime/_findCrcOne.finishedSize*((1<<32)-_findCrcOne.finishedSize)),
            file=sys.stderr);

def _findCrcMulti(data, target):
    # compile SearchCRC.cpp to libSearchCRC.so
    if not os.path.exists("./libSearchCRC.so"):
        from shutil import which
        for cmd in ("cc", "gcc", "clang++", ""):
            if which(cmd):
                break;
        if not cmd:
            raise Exception("Can't find c++ compiler");
        os.system(cmd+" SearchCRC.cpp -fPIC -shared -o libSearchCRC.so -O3");
        assert os.path.exists("./libSearchCRC.so");

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    poses=[m.start() for m in re.finditer(b"0000", data)];

    threads=[];
    step=(1<<32)//16;
    for L in range(0, 1<<32, step):
        threads.append(threading.Thread(
            target=_findCrcOne,
            args=(data, target, poses, L, min(L+step, 1<<32))));
        threads[-1].start();
    for t in threads:
        t.join();

    for p in poses:
        data=data[:p]+_findCrcOne.finalAns.to_bytes(4, "little")+data[p+4:];
    assert binascii.crc32(data)==target;
    return data;

################################

if __name__=="__main__":
    if len(sys.argv)!=3:
        print("Usage: {} <output file> <file should be included>".format(sys.argv[0]));
        sys.exit(1);
    QuineGenerate(sys.argv[1], sys.argv[2]);
