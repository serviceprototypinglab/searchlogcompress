# Module for searchable log compression

import sys
import re

def slc_eightfive(text, verbose=False):
    stack = []
    rstack = []
    for c in text:
        if c.islower():
            pos = ord(c) - ord("a")
            if verbose:
                print(c, pos, "{:05b}".format(pos))
            stack.append(pos)
        else:
            if verbose:
                print("// stack", stack)
            if len(stack) >= 3:
                lastz = 0
                bits = 0
                hangover = False
                for z in stack + [0, 0]:
                    if verbose:
                        print("B", bits, "@", z)
                    if hangover:
                        hangover = False
                        lastz = z
                        continue
                    if bits % 8:
                        rs = 5 - (8 - bits)
                        if verbose:
                            print("stuff/left-shift '", lastz, "' by", 8 - bits, "bits and filter/right-shift", z, "by", rs, "bits")
                        lastz = lastz << (8 - bits)
                        if rs > 0:
                            lastz |= z >> rs
                        elif rs < 0:
                            lastz |= z << -rs
                        else:
                            lastz |= z
                        #rstack.append(chr(lastz))
                        lastzrest = 0
                        if rs > 0:
                            if verbose:
                                print("RS", rs)
                            lastzrest = z & (2 ** rs) - 1
                        if rs >= 0:
                            f = "{:0" + str(rs) + "b}"
                        else:
                            f = "--{}"
                            bits -= 3 # ? works not sure why
                        if rs >= 0:
                            if verbose:
                                print("P", lastz, "{:08b}".format(lastz), "rest", f.format(lastzrest))
                            rstack.append(chr(lastz))
                        else:
                            if verbose:
                                print("P-tmp", lastz, "{:08b}".format(lastz), "rest", f.format(lastzrest))
                            hangover = True
                        lastz = lastzrest
                    else:
                        lastz = z
                    bits = (bits + 5) % 8
                stack = []
            if verbose:
                print("*", c)
            rstack += [chr(x + ord("a")) for x in stack]
            stack = []
            rstack.append(c)
    return "".join(rstack)

def coolencode_numeric(s):
    cs = ""
    d = ""
    for c in s:
        if c.isdigit():
            d += c
        else:
            if d:
                try:
                    cs += chr(int(d))
                except:
                    # out of unicode range
                    cs += d
            d = ""
            cs += c
    if d:
        try:
            cs += chr(int(d))
        except:
            # out of unicode range
            cs += d
    return cs

def coolencode_ipv4(s):
    cs = ""
    iprot = -1
    for i in range(len(s)):
        if i < iprot:
            continue
        if i < len(s) - 6 and s[i + 1] == "." and s[i + 3] == "." and s[i + 5] == ".":
            cs += s[i] + s[i + 2] + s[i + 4] + s[i + 6]
            iprot = i + 6
        else:
            cs += s[i]
    return cs

def coolencode_timestamp(s):
    cs = ""
    iprot = -1
    for i in range(len(s)):
        if i < iprot:
            continue
        if i < len(s) - 7 and s[i].isdigit() and s[i + 1].isdigit() and s[i + 3].isdigit() and s[i + 4].isdigit():
            if s[i + 6].isdigit() and s[i + 7].isdigit() and s[i + 2] == ":" and s[i + 5] == ":":
                #print("stamp", s[i:i+8])
                cs += chr(int(s[i:i+2])) + chr(int(s[i+3:i+5])) + chr(int(s[i+6:i+8]))
                iprot = i + 7
        if iprot <= i:
            cs += s[i]
    return cs

def coolencode(s, verbose=False):
    s2 = coolencode_timestamp(s)
    s3 = coolencode_ipv4(s2)
    s4 = coolencode_numeric(s3)
    #s4 = s3 # !!! numeric makes problems in file writing
    s5 = slc_eightfive(s4)
    if verbose:
        print("s:orig", s)
        print("s:ipv4", s2)
        print("s:nume", s3)
        print("s:time", s4)
        print("s:8to5", s5)
    return s5

def search(t, st):
    print("search", st)
    print("find @", t.index(coolencode(st)))

def test_coolencode():
    f = open("../../logdata.gitlab/head1000-admin.log")
    fw = open("head1000-admin.bin", "w")
    b = 0
    bc = 0
    errs = 0
    for line in f:
        line = line.strip()
        linec = coolencode(line)
        b += len(line) + 1
        bc += len(linec) + 1
        try:
            print(linec, file=fw)
        except:
            errs += 1
    fw.close()
    f.close()
    print("capacity over logfile", b, "bytes to", bc, "bytes; capacity saved:", round(100 * (1 - bc / b)), "%")
    print("!! errors:", errs)

if __name__ == "__main__":
    test_coolencode()
