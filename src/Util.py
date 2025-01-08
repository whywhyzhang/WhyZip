import DynamicOP

import struct
import datetime

#######################################

class BitStream:
    def __init__(self, data : bytes):
        self.data=data;
        self.cacheBits='';

    def TryReadBits(self, size):
        self._toCacheBits(size);
        return self.cacheBits[:size];

    def ReadBits(self, size):
        self._toCacheBits(size);
        ret=self.cacheBits[:size];
        self.cacheBits=self.cacheBits[size:];
        return ret;

    def ReadInt(self, size, bitOrder="big"):
        bits=self.ReadBits(size);
        return BitStream.Bits2Int(bits, bitOrder);

    def AlignBytes(self):
        self.cacheBits=self.cacheBits[len(self.cacheBits)%8:];

    def BitLen(self):
        return len(self.cacheBits)+len(self.data)*8;

    def _toCacheBits(self, size):
        while len(self.cacheBits)<size:
            self.cacheBits+="{:08b}".format(self.data[0])[::-1];
            self.data=self.data[1:];
    
    def Bits2Int(bits, bitOrder="big"):
        if bitOrder=="big":
            return int(bits[::-1], 2);
        return int(bits, 2);

    def Int2Bits(x, size, bitOrder="big"):
        ret="{1:0{0}b}".format(size, x);
        if bitOrder=="big":
            return ret;
        return ret[::-1];

class Huffman:
    def __init__(self, buildType, *args):
        self.code2val={};
        if buildType==1:
            self._buildType1(*args);
        elif buildType==2:
            self._buildType2(*args);

        self.maxCodeLen=0;
        self.val2code={};
        for k, v in self.code2val.items():
            self.val2code[v]=k;
            self.maxCodeLen=max(self.maxCodeLen, len(k));

    def DecodeOne(self, bits : BitStream):
        for i in range(1, min(self.maxCodeLen, bits.BitLen())+1):
            if bits.TryReadBits(i) in self.code2val:
                return self.code2val[bits.ReadBits(i)];
        raise Exception("Invalid Huffman code: {}".format(bits.TryReadBits(self.maxCodeLen)));

    def EncodeOne(self, val):
        return self.val2code[val];

    # [(L, R, bit, codeL), ...]
    def _buildType1(self, fmts):
        for L, R, bit, codeL in fmts:
            codeL=int(codeL, 2);
            for i in range(L, R+1):
                # self.code2val["{0:0{1}b}".format(bit, codeL+i)]=codeL;
                self.code2val["{0:0{1}b}".format(codeL+i-L, bit)]=i;

    # [len0, len1, ...]
    def _buildType2(self, lens):
        len2cnt={};
        for l in lens:
            len2cnt.setdefault(l, 0);
            len2cnt[l]+=1;
        len2cnt[0]=0;
        nextCodes=[0]*(max(lens)+1);
        for i in range(1, max(lens)+1):
            nextCodes[i]=(nextCodes[i-1]+len2cnt.get(i-1, 0))<<1;
        for i, l in enumerate(lens):
            if l==0:
                continue;
            self.code2val["{0:0{1}b}".format(nextCodes[l], l)]=i;
            nextCodes[l]+=1;

class ExtraNumber:
    # [(L, R, extraBit, valL), ...]
    def __init__(self, fmts):
        self.code2extra={};
        for L, R, extraBit, valL in fmts:
            for i in range(L, R+1):
                v=valL+((i-L)<<extraBit);
                self.code2extra[i]=(extraBit, v);

    def DecodeCode(self, code, bits: BitStream):
        extraBit, valL=self.code2extra[code];
        if extraBit>0:
            tmp=bits.ReadInt(extraBit);
            valL+=tmp;
        return valL;

    def EncodeCode(self, val):
        for c, (e, vL) in self.code2extra.items():
            if val>=vL:
                code, extraBit, valL=(c, e, vL);
            else:
                break;
        if extraBit==0:
            assert val==valL;
            return code, '';
        return code, BitStream.Int2Bits(val-valL, extraBit);

#######################################

# Reference: https://www.rfc-editor.org/rfc/rfc1951.html

staticHL=Huffman(1, [
    (0, 143, 8, "00110000"),
    (144, 255, 9, "110010000"),
    (256, 279, 7, "0000000"),
    (280, 287, 8, "11000000"),
]);

staticHD=Huffman(1, [
    (0, 31, 5, "00000"),
]);

staticLen=ExtraNumber([
    (257, 264, 0, 3),
    (265, 268, 1, 11),
    (269, 272, 2, 19),
    (273, 276, 3, 35),
    (277, 280, 4, 67),
    (281, 284, 5, 131),
    (285, 285, 0, 258),
]);

staticDist=ExtraNumber([
    (0, 3, 0, 1),
    (4, 5, 1, 5),
    (6, 7, 2, 9),
    (8, 9, 3, 17),
    (10, 11, 4, 33),
    (12, 13, 5, 65),
    (14, 15, 6, 129),
    (16, 17, 7, 257),
    (18, 19, 8, 513),
    (20, 21, 9, 1025),
    (22, 23, 10, 2049),
    (24, 25, 11, 4097),
    (26, 27, 12, 8193),
    (28, 29, 13, 16385),
]);

staticLevel=ExtraNumber([
    (17, 17, 3, 3),
    (18, 18, 7, 11),
]);

#######################################

def GetMsDOSDateTime():
    now=datetime.datetime.now();
    _time=int("{:05b}{:06b}{:05b}".format(now.hour, now.minute, now.second//2), 2);
    _date=int("{:07b}{:04b}{:05b}".format(now.year-1980, now.month, now.day), 2);
    return (_date, _time);

class ZipDeco:
    class SIGN: pass;
    class UInt8: pass;
    class UInt16: pass;
    class UInt32: pass;
    class LenBytes: pass;

    def __call__(self, cls):
        anno2fmtSize={
            ZipDeco.SIGN: ("I", 4),
            ZipDeco.UInt8: ("B", 1),
            ZipDeco.UInt16: ("H", 2),
            ZipDeco.UInt32: ("I", 4),
        };
        cls._fmts=[];
        cls._baseLen=0;
        cls._exLens=[];
        cls._defaultDict={};
        for a, b in cls.__dict__.items():
            if a.startswith("_") or callable(b):
                continue;
            anno=cls.__annotations__[a];
            if anno in anno2fmtSize:
                cls._defaultDict[a]=b;
                cls._baseLen+=anno2fmtSize[anno][1];
                cls._fmts.append((a, anno2fmtSize[anno][0]));
            elif anno==ZipDeco.LenBytes:
                cls._defaultDict[a]=b'';
                cls._exLens.append(b);
                cls._fmts.append((a, 's'+b));
            else:
                raise Exception("Unknown type: {}".format(type(b)));

        cls.__init__=ZipDeco._init;
        cls.Pack=ZipDeco.Pack;
        cls.PackSize=ZipDeco.PackSize;
        return cls;

    def _init(self, **dd):
        self.__dict__=self._defaultDict.copy();
        for k, v in dd.items():
            assert k in self.__dict__;
            self.__dict__[k]=v;

    def Pack(self) -> bytes:
        ret=[];
        for name, f in self._fmts:
            val=getattr(self, name);
            if f[0]=='s':
                f='<'+str(len(val))+'s';
            else:
                f='<'+f;
            ret.append(struct.pack(f, val));
        return b''.join(ret);

    def PackSize(self) -> int:
        return self._baseLen+sum(getattr(self, e) for e in self._exLens);

#######################################

# Reference: https://pkwaredownloads.blob.core.windows.net/pkware-general/Documentation/APPNOTE-6.3.9.TXT

@ZipDeco()
class ECD:
    SIGN           : ZipDeco.SIGN     = 0x06054b50;
    numDisk        : ZipDeco.UInt16   = 0;
    numDiskCD      : ZipDeco.UInt16   = 2;
    numEntriesDisk : ZipDeco.UInt16   = 1;
    numEntries     : ZipDeco.UInt16   = 1;
    sizeCD         : ZipDeco.UInt32   = None;
    offsetCD       : ZipDeco.UInt32   = None;
    sizeComment    : ZipDeco.UInt16   = 0;
    comment        : ZipDeco.LenBytes = "sizeComment";

@ZipDeco()
class CD:
    SIGN                   : ZipDeco.SIGN     = 0x02014b50;
    version                : ZipDeco.UInt16   = 31;
    versionNeeded          : ZipDeco.UInt16   = 20;
    flag                   : ZipDeco.UInt16   = 0;
    compression            : ZipDeco.UInt16   = 0;
    lastModTime            : ZipDeco.UInt16   = GetMsDOSDateTime()[1];
    lastModDate            : ZipDeco.UInt16   = GetMsDOSDateTime()[0];
    crc32                  : ZipDeco.UInt32   = None;
    compressedSize         : ZipDeco.UInt32   = None;
    uncompressedSize       : ZipDeco.UInt32   = None;
    fileNameLength         : ZipDeco.UInt16   = None;
    extraFieldLength       : ZipDeco.UInt16   = 0;
    fileCommentLength      : ZipDeco.UInt16   = 0;
    diskNumberStart        : ZipDeco.UInt16   = 0;
    internalFileAttributes : ZipDeco.UInt16   = 0;
    externalFileAttributes : ZipDeco.UInt32   = 32;
    relativeOffset         : ZipDeco.UInt32   = None;
    fileName               : ZipDeco.LenBytes = "fileNameLength";
    extraField             : ZipDeco.LenBytes = "extraFieldLength";
    fileComment            : ZipDeco.LenBytes = "fileCommentLength";

@ZipDeco()
class LocalFile:
    SIGN             : ZipDeco.UInt32   = 0x04034b50;
    version          : ZipDeco.UInt16   = 20;
    flag             : ZipDeco.UInt16   = 0;
    compression      : ZipDeco.UInt16   = 0;
    lastModTime      : ZipDeco.UInt16   = GetMsDOSDateTime()[1];
    lastModDate      : ZipDeco.UInt16   = GetMsDOSDateTime()[0];
    crc32            : ZipDeco.UInt32   = None;
    compressedSize   : ZipDeco.UInt32   = None;
    uncompressedSize : ZipDeco.UInt32   = None;
    fileNameLength   : ZipDeco.UInt16   = None;
    extraFieldLength : ZipDeco.UInt16   = 0;
    fileName         : ZipDeco.LenBytes = "fileNameLength";
    extraField       : ZipDeco.LenBytes = "extraFieldLength";

@ZipDeco()
class DataDescriptor:
    SIGN             : ZipDeco.UInt32 = 0x08074b50;
    crc32            : ZipDeco.UInt32 = None;
    compressedSize   : ZipDeco.UInt32 = None;
    uncompressedSize : ZipDeco.UInt32 = None;

#######################################

class Element:
    # BYTES: b'abcd'
    # PH: (len(bytes), id)
    # RAW: len
    # OP: (DIST, LEN, BITS)
    def __init__(self, t, *attr):
        self.type=t;
        self.attr=attr;
        self.fromCode=None;

    def __eq__(self, b):
        return self.type==b.type and self.attr==b.attr;

    def __str__(self):
        if self.type=="BYTES":
            return str(len(self.attr))+':'+str(self.attr);
        if self.type=="PH":
            return "PH{}_{}".format(*self.attr);
        if self.type=="RAW":
            return "R{:04x}".format(*self.attr);
        if self.type=="OP":
            tmp="O{:02x}{:02x}".format(self.attr[0], self.attr[1]);
            tmp+='_'*(self.attr[2]-len(tmp));
            return tmp;
        raise Exception("Unknown type {}".format(self.type));

    def __len__(self):
        if self.type=="BYTES":
            return len(self.attr);
        if self.type=="PH":
            return self.attr[0];
        if self.type=="RAW":
            return 5;
        if self.type=="OP":
            return self.attr[2];
        raise Exception("Unknown type {}".format(self.type));

    def IsFinal(self):
        return self.fromCode is not None and self.fromCode.isFinal;

    def ToBinary(self, phId2Bytes={}) -> bytes:
        if self.type=="BYTES":
            return self.attr[0];
        if self.type=="PH":
            if isinstance(self.attr[1], int):
                return phId2Bytes[self.attr[1]];
            return b''.join(x.ToBinary(phId2Bytes) for x in self.attr[1]);
        if self.type=="RAW":
            ret=b'\x01' if self.IsFinal() else b'\x00';
            ret+=self.attr[0].to_bytes(2, "little");
            ret+=((~self.attr[0]) & 0xFFFF).to_bytes(2, "little");
            return ret;
        if self.type=="OP":
            exRawNum, tmp=DynamicOP.Find(*self.attr);

            ret=['1' if self.IsFinal() and exRawNum==0 else '0', "10"];
            for t in tmp:
                code, bits=staticLen.EncodeCode(t);
                bits=staticHL.EncodeOne(code)+bits[::-1];
                code, bits1=staticDist.EncodeCode(self.attr[0]);
                bits1=staticHD.EncodeOne(code)+bits1[::-1];
                ret.append(bits+bits1);
            ret.append("0000000")
            ret=''.join(ret);

            if len(ret)%8:
                ret+="100" if self.IsFinal() and exRawNum==1 else "000";
                ret+='0'*((8-len(ret)%8)%8)+'0'*16+'1'*16;
                exRawNum-=1;
            for i in range(exRawNum):
                ret+=('1' if self.IsFinal() and i==exRawNum-1 else '0')+'0'*23+'1'*16;

            ret=[int(ret[i:i+8][::-1], 2) for i in range(0, len(ret), 8)];
            ret=[x.to_bytes(1, "little") for x in ret];
            return b''.join(ret);
        raise Exception("Unknown type {}".format(self.type));

class Code:
    def __init__(self, type, *attr):
        self.type=type;
        self.isFinal=False;
        if self.type=="RAW":
            for a in attr:
                assert isinstance(a, Element);
        self.attr=attr;

    def __repr__(self):
        ret=self.type;
        for e in self.attr:
            ret+=' '+str(e);
        return ret;

    def __len__(self):
        ret=len(self.ToElement());
        if self.type=="RAW":
            ret+=sum(len(x) for x in self.attr);
        return ret;

    def ToElement(self) -> Element:
        if self.type=="RAW":
            ret=Element("RAW", sum(len(x) for x in self.attr));
            ret.fromCode=self;
            return ret;
        if self.type=="OP":
            ret=Element("OP", *self.attr);
            ret.fromCode=self;
            return ret;
        raise Exception("Unknown type {}".format(self.type));

    def ToCode(self) -> str:
        if self.type=="RAW":
            tmp=self.ToOutput();
            return str(self.ToElement())+' '+len(tmp)+' '+tmp;
        if self.type=="OP":
            return str(self.ToElement());
        raise Exception("Unknown type {}".format(self.type));

    def ToOutput(self) -> str:
        if self.type=="RAW":
            return ''.join([str(x) for x in self.attr]);
        raise Exception("Unknown type {}".format(self.type));

    def ToBinary(self, phId2Bytes) ->bytes:
        if self.type=="RAW":
            return (self.ToElement().ToBinary()+b''.join(
                x.ToBinary(phId2Bytes) for x in self.attr));
        elif self.type=="OP":
            return self.ToElement().ToBinary();
        raise Exception("Unknown type {}".format(self.type));
