# Prototype for searchable log compression.
# Syntax: slcreader.py <logfile> <logcontext> [http|slcp] # inprocess/client
#         - if <logfile> is <search:phrase>, then search for <phrase>
#         - otherwise, process lines from <logfile>
#         slcreader.py slcp # server, pairs with slcp client mode
# SLCP: Searchable Logfile Compression Protocol (port 7777)
# % netcat -l -p 7777
# % python3 slcreader.py ../head1000-admin.log adminlog slcp

import time
import urllib.request
import sys
import slcmod
import os
import json
import socket

class SLC:
    PROTO_INPROCESS = 101
    PROTO_SLCP = 102
    PROTO_HTTP = 103

    def __init__(self):
        self.day = None
        self.time = None
        self.b = 0
        self.bc = 0
        self.errs = 0
        self.succ = 0
        self.authenticated = False
        self.context = None

    def authenticate(self, token):
        try:
            f = open("authtoken.secret")
            secret = f.readline().strip()
        except:
            print("Error: Cannot open secret file!", file=sys.stderr)
            return
        else:
            f.close()
        if token == secret:
            print("SLC: Authenticated.")
            self.authenticated = True
        else:
            print("Error: Secret token not matching!", file=sys.stderr)
        return self.authenticated

    def setcontext(self, ctx):
        if not ctx.isalpha():
            print("Error: Context is not an alphabetic word!", file=sys.stderr)
            return False
        print(f"SLC: Context set to {ctx}.")
        self.context = ctx

        datafolder = "reader.persistence"
        metafile = f"{datafolder}/{self.context}.meta"
        if os.path.isfile(metafile):
            fmeta = open(metafile)
            meta = json.load(fmeta)
            fmeta.close()
            self.b = meta["b"]
            self.bc = meta["bc"]
            self.succ = meta["succ"]
            self.errs = meta["errs"]
            print("SLC: Continue previous session.")

        return True

    def process(self, line):
        if not self.authenticated:
            print("Error: Not authenticated!", file=sys.stderr)
            return
        if not self.context:
            print("Error: No context defined!", file=sys.stderr)
            return

        datafolder = "reader.persistence"

        linec = slcmod.coolencode(line)
        self.b += len(line) + 1
        self.bc += len(linec) + 1
        printable = True
        os.makedirs(datafolder, exist_ok=True)
        fw = open(f"{datafolder}/{self.context}.bin", "a")
        try:
            print(linec, file=fw)
        except:
            printable = False
            self.errs += 1
        else:
            self.succ += 1
        fw.close()
        print(f"SLC: {self.b:7} → {self.bc:7} bytes; printable: {printable:5}; total {self.succ:5} out of {self.succ + self.errs:5}; {line[:40]}...")

        meta = {"b": self.b, "bc": self.bc, "succ": self.succ, "errs": self.errs}
        fmeta = open(f"{datafolder}/{self.context}.meta", "w")
        json.dump(meta, fmeta)
        fmeta.close()

        return linec

    def search(self, searchterm):
        #print("SEARCH FOR", searchterm)
        if not self.authenticated:
            print("Error: Not authenticated!", file=sys.stderr)
            return
        if not self.context:
            print("Error: No context defined!", file=sys.stderr)
            return

        stc = slcmod.coolencode(searchterm)

        datafolder = "reader.persistence"
        fs = open(f"{datafolder}/{self.context}.bin")
        counter = 0
        for linec in fs:
            try:
                #print("#@", linec.index(stc))
                counter += 1
            except:
                pass
                #print("#@---")
        fs.close()
        print(f"SLC: {counter} results for term {searchterm}.")
        return counter

def main(logfile, token, ctx, proto):
    def ubytes(s):
        return bytes(s, "utf-8")

    readresponse = False

    if proto == SLC.PROTO_INPROCESS:
        sl = SLC()
        sl.authenticate(token)
        sl.setcontext(ctx)
    elif proto == SLC.PROTO_SLCP:
        s = socket.socket()
        s.connect(("localhost", 7777))
        authreq = ubytes(f"AUTH {token}\n")
        s.send(authreq)
        ctxreq = ubytes(f"CONTEXT {ctx}\n")
        s.send(ctxreq)

    if logfile.startswith("search:"):
        readresponse = True
        searchterm = logfile[7:]
        if proto == SLC.PROTO_INPROCESS:
            r = sl.search(searchterm)
            print("Results>>", r)
        elif proto == SLC.PROTO_SLCP:
            searchreq = ubytes(f"SEARCH {searchterm}\n")
            s.send(searchreq)
    else:
        f = open(logfile)
        for line in f:
            line = line.strip()

            if proto == SLC.PROTO_INPROCESS:
                sl.process(line)
                time.sleep(2)
            elif proto == SLC.PROTO_SLCP:
                procreq = ubytes(f"PROCESS {line}\n")
                s.send(procreq)

    if proto == SLC.PROTO_SLCP:
        if readresponse:
            # FIXME might need waiting time on real network
            inb = s.recv(5000)
            if inb:
                print("Response>>", inb.decode().strip())
        s.close()

def run_slcp():
    print("» SLCP starting...")
    sl = SLC()
    smain = socket.socket()
    smain.bind(("localhost", 7777))
    smain.listen(1)
    s, saddr = smain.accept()
    print("» SLCP", s.fileno(), saddr)
    rest = b""
    while True:
        inb = s.recv(5000)
        if not inb:
            print("» SLCP interrupted")
            return
        inbs = inb.split(b"\n")
        print("» SLCP received lines:", len(inbs))
        inbs[0] = rest + inbs[0]
        rest = inbs[-1]
        for inb in inbs[:-1]:
            print("-", inb[:40], "...")
            ins = inb.decode()
            cmd, *args = ins.split(" ")
            args = " ".join(args)
            if cmd == "AUTH":
                r = sl.authenticate(args)
                if not r:
                    s.send(bytes("ERROR auth\n", "utf-8"))
                    return
            elif cmd == "CONTEXT":
                r = sl.setcontext(args)
                if not r:
                    s.send(bytes("ERROR context\n", "utf-8"))
                    return
            elif cmd == "PROCESS":
                r = sl.process(args)
                if r is None:
                    s.send(bytes("ERROR process\n", "utf-8"))
                    return
            elif cmd == "SEARCH":
                r = sl.search(args)
                if r is None:
                    s.send(bytes("ERROR search\n", "utf-8"))
                    return
                s.send(bytes(f"RESULTS {r}\n", "utf-8"))
            else:
                s.send(bytes("ERROR cmd\n", "utf-8"))
                return
        print("» SLCP keep remainder:", len(rest), "bytes")

def mainwrapper():
    logfile = "../head1000-admin.log"
    if len(sys.argv) >= 2:
        logfile = sys.argv[1]

    if logfile == "slcp":
        run_slcp()
        return

    ctx = "adminlog"
    if len(sys.argv) >= 3:
        ctx = sys.argv[2]

    proto = SLC.PROTO_INPROCESS
    if len(sys.argv) == 4:
        protostr = sys.argv[3]
        if protostr == "http":
            proto = SLC.PROTO_HTTP
        elif protostr == "slcp":
            proto = SLC.PROTO_SLCP
        else:
            print("Unsupported protocol!", file=sys.stderr)
            return

    f = open("authtoken.secret")
    token = f.readline().strip()
    f.close()

    main(logfile, token, ctx, proto)

if __name__ == "__main__":
    mainwrapper()
