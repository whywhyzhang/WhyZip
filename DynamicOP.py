import bisect

# Use Dynamic Programming to find the minimum length of OP code
def SearchMin(l):
    INF=1<<32;
    ret=[0]*5;
    base=_searchAllLen(l);
    for dLen in range(5, 19):
        tmp=[INF]*5;
        one=set([_toBlockSize(x[0]*dLen+x[1])[0]//8 for x in base]);
        for x in one:
            tmp[x%5]=min(tmp[x%5], x);
        for i in range(5):
            ret[i]=max(ret[i], tmp[i]);
    ret=min(ret);
    assert ret<INF;
    return ret;

# Find the OP code path, after use SearchMin to get the minimum length
def Find(d, l, byteLen):
    dLen=_dist2BitLen(d);
    ans=_searchAllLen(l);
    for one in ans:
        tmp, rawCnt=_toBlockSize(one[0]*dLen+one[1]);
        tmp//=8;
        if tmp>byteLen or (byteLen-tmp)%5:
            continue;
        return rawCnt+(byteLen-tmp)//5, _findPath(one, l);
    raise Exception("Can't find OP: ({} {} {})".format(d, l, byteLen));

def _findPath(now, l):
    ret=[];
    while l>0:
        ret.append(now[2]);
        l-=now[2];
        next=_searchAllLen(l);
        for one in next:
            if one[0]+1==now[0] and one[1]+_len2BitLen(now[2])==now[1]:
                now=one;
                break;
    return ret;

def _searchAllLen(l):
    if l==0:
        return [(0, 0)];
    if l in _searchAllLen._REM:
        return _searchAllLen._REM[l];

    ans={};
    for nl in range(3, l+1):
        tmp=_searchAllLen(l-nl);
        y=_len2BitLen(nl);
        for x in tmp:
            ans[(x[0]+1, x[1]+y)]=nl;
    ans=[(k[0], k[1], v) for k, v in ans.items()];
    _searchAllLen._REM[l]=ans;
    return ans;
_searchAllLen._REM={};

def _toBlockSize(x):
    x+=10;
    if x%8==0:
        return x, 0;
    x+=3;
    return x+(8-x%8)%8+32, 1;

def _dist2BitLen(d):
    assert d>=1 and d<=32768;
    dist2bit=list({
        4: 5,       8: 6,       16: 7,      32: 8,
        64: 9,      128: 10,    256: 11,    512: 12,
        1024: 13,   2048: 14,   4096: 15,   8192: 16,
        16384: 17,  32768: 18,
    }.items());
    return dist2bit[bisect.bisect_right(dist2bit, (d, 0))][1];

def _len2BitLen(l):
    assert l>=3 and l<=258;
    len2bit=list({
        10: 7,      18: 8,      34: 9,      66: 10,
        114: 11,    130: 12,    257: 13,    258: 8,
    }.items());
    return len2bit[bisect.bisect_right(len2bit, (l, 0))][1];
