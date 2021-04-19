#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
import json
import re
import subprocess
import time
import json
from collections import defaultdict
from pwd import getpwnam
from datetime import timedelta

duration_re = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+([.]{1}\d+){0,1}?)s)?')


def parse_time(time_str):
    parts = duration_re.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = float(param)
    return timedelta(**time_params)


def replace_file(filename, s, print_f=True):
    with open(filename, "w+") as f:
        f.seek(0)
        f.truncate()
        f.write(s)

    if print_f:
        with open(filename, "r") as f:
            print(f.read())
            print('-' * 80)
    print(f"[*] write {filename} done")
    print('-' * 80)
    print('\n')


def retry(func, max_times: int, interval: int):
    for i in range(max_times):
        try:
            func()
            break
        except BaseException as e:
            if i < (max_times - 1):
                print(f"do {func.__name__} failed: {e}, will try again in {interval} seconds")
                time.sleep(interval)
                continue
            else:
                raise Exception(f"do {func.__name__} failed due to {e}")

def gen_run_lotus():
    s = f"""#!/bin/bash
set -e

S=star
V={VERSION}

sleep 10

#echo 8222172 | sudo tee /proc/sys/kernel/threads-max
#echo 8388608 | sudo tee /proc/sys/vm/max_map_count
#echo 1000000 | sudo tee /proc/sys/kernel/pid_max
#echo 1000000 | sudo tee /sys/fs/cgroup/pids/user.slice/user-1000.slice/pids.max

export RUST_BACKTRACE=full
export RUST_LOG=info
export GOLOG_LOG_FMT=json

export LOTUS_PATH="/home/{USER}/share/ssd/data/lotus_$V"

export IPFS_GATEWAY="https://filestar-proofs.s3.cn-east-1.jdcloud-oss.com/ipfs/"
export FIL_PROOFS_PARAMETER_CACHE="/home/{USER}/share/ssd/data/filecoin-proof-parameters"

unset FIL_PROOFS_MAXIMIZE_CACHING
export SKIP_BASE_EXP_CACHE=1

mkdir -p /home/{USER}/share/ssd/bin/bin_$V/
cp /home/{USER}/share/ssd/bin/bin_$S/lotus /home/{USER}/share/ssd/bin/bin_$V/
/home/{USER}/share/ssd/bin/bin_$V/lotus daemon &
sudo prlimit --nofile=1048576 --nproc=unlimited --rtprio=99 --nice=-19 --pid $!

wait
    """
    filename = os.path.join(SCRIPT_PATH, f"run_lotus_{VERSION}.sh")
    replace_file(filename, s)
    subprocess.check_call(f"chmod +x {filename}", shell=True)


def lotus_superv_conf():
    s = f"""[program:lotus_{VERSION}]
command=/home/{USER}/share/ssd/script/run_lotus_{VERSION}.sh
user={USER}

autostart=true
autorestart=true
stopwaitsecs=60
startretries=100
stopasgroup=true
killasgroup=true
priority=990

redirect_stderr=true
stdout_logfile=/home/{USER}/share/hdd/log/lotus_{VERSION}.log
stdout_logfile_maxbytes=512MB
stdout_logfile_backups=20
"""
    filename = "/etc/supervisor/conf.d/lotus.conf"
    replace_file(filename, s)


def update_lotus_config():
    s = f"""# Default config:
[API]
ListenAddress = "/ip4/{LOCAL_IP}/tcp/{LOTUS_API_LISTEN}/http"
#  RemoteListenAddress = ""
#  Timeout = "30s"
#
[Libp2p]
ListenAddresses = ["/ip4/0.0.0.0/tcp/{LOTUS_P2P_LISTEN}", "/ip6/::/tcp/{LOTUS_P2P_LISTEN}"]
#  AnnounceAddresses = []
#  NoAnnounceAddresses = []
#  ConnMgrLow = 150
#  ConnMgrHigh = 180
#  ConnMgrGrace = "20s"
#
[Pubsub]
#  Bootstrapper = false
#  RemoteTracer = "/ip4/147.75.67.199/tcp/4001/p2p/QmTd6UvR47vUidRNZ1ZKXHrAFhqTJAD27rKL9XYghEKgKX"
#
[Client]
#  UseIpfs = false
#  IpfsMAddr = ""
#  IpfsUseForRetrieval = false
#
[Metrics]
#  Nickname = ""
#  HeadNotifs = false
#
    """
    replace_file(os.path.join(DATA_PATH, f"lotus_{VERSION}/config.toml"), s)


def update_lotus_api():
    dest = os.path.join(DATA_PATH, 'lotus')
    if not os.path.exists(dest):
        os.mkdir(dest)
    api = os.path.join(DATA_PATH, 'lotus_{}/api'.format(VERSION))
    with open(api, 'r') as f:
        text = f.read()
        if str(LOTUS_API_LISTEN) not in text:
            raise BaseException("lotus api not updated")
    subprocess.check_call(f"cp {api} {dest}", shell=True)
    subprocess.check_call(f"cp {os.path.join(DATA_PATH, 'lotus_{}/token'.format(VERSION))} {dest}", shell=True)
    os.system(f"cat {os.path.join(dest, 'api')}")
    print("\n")


def gen_init_miner():
    owner = subprocess.check_output("lotus wallet default", universal_newlines=True, shell=True).strip()
    if not owner:
        raise Exception("lotus wallet default not set")
    miner = input("miner id (leave this empty to create new):").strip()
    if miner:
        payload = f"/home/{USER}/share/ssd/bin/bin_$V/lotus-miner init --owner=$O --actor={miner}"
    else:
        payload = f"/home/{USER}/share/ssd/bin/bin_$V/lotus-miner init --owner=$O --sector-size={SECTOR_SIZE}GiB"

    s = f"""#!/bin/bash
S=star
V={VERSION}
O={owner}

export RUST_BACKTRACE=full
export RUST_LOG=trace
export GOLOG_LOG_FMT=json

export TRUST_PARAMS=1
export LOTUS_PATH="/home/{USER}/share/ssd/data/lotus_$V"
export LOTUS_MINER_PATH="/home/{USER}/share/ssd/data/lotusminer_$V"

export IPFS_GATEWAY="https://filestar-proofs.s3.cn-east-1.jdcloud-oss.com/ipfs/"
export FIL_PROOFS_PARAMETER_CACHE="/home/{USER}/share/ssd/data/filecoin-proof-parameters"

unset FIL_PROOFS_MAXIMIZE_CACHING
export SKIP_BASE_EXP_CACHE=1

mkdir -p /home/{USER}/share/ssd/bin/bin_$V
cp /home/{USER}/share/ssd/bin/bin_$S/lotus-miner /home/{USER}/share/ssd/bin/bin_$V/
{payload}
    """
    filename = os.path.join(SCRIPT_PATH, f'init_miner_{VERSION}.sh')
    replace_file(filename, s)
    subprocess.check_call(f"chmod +x {filename}", shell=True)


def gen_default_filter():
    s = """#!/usr/bin/perl

use warnings;
use strict;
use 5.014;

# Uncomment this to lock down the miner entirely
#exit 1

# A list of wallets you do not want to deal with
# For example this enty will prevent a shady ribasushi
# character from storing things on your miner
my $denylist = { map {( $_ => 1 )} qw(
  t3vxr6utzqjobnjnhi5gwn7pqoqstw7nrh4kchft6tzb2e7xorwvj5f3tg3du3kedadtkxvyp4jakf3zdd4iaa
)};

use JSON::PP 'decode_json';

my $deal = eval { decode_json(do{ local $/; <> }) };
if( ! defined $deal ) {
  print "Deal proposal JSON parsing failed: $@";
  exit 1;
}

if( $denylist->{$deal->{Proposal}{Client}} ) {
  print "Deals from client wallet $deal->{Proposal}{Client} are not welcome";
  exit 1;
}

exit 0;
    """
    replace_file(FILTER_PATH, s)
    subprocess.check_call(f"chmod +x {FILTER_PATH}", shell=True)


def update_miner_config():
    if not os.path.exists(FILTER_PATH):
        raise Exception(f"{FILTER_PATH} not found")
    
    s = f"""# Default config:
[API]
ListenAddress = "/ip4/{LOCAL_IP}/tcp/2819/http"
RemoteListenAddress = "{LOCAL_IP}:2819"
#  Timeout = "30s"
#
[Libp2p]
#  ListenAddresses = ["/ip4/0.0.0.0/tcp/{MINER_P2P_LISTEN}"]
#  AnnounceAddresses = []
#  NoAnnounceAddresses = []
#  ConnMgrLow = 896
#  ConnMgrHigh = 1024
#  ConnMgrGrace = "20s"
#
[Pubsub]
#  Bootstrapper = false
#  RemoteTracer = "/ip4/147.75.67.199/tcp/4001/p2p/QmTd6UvR47vUidRNZ1ZKXHrAFhqTJAD27rKL9XYghEKgKX"
#
[Dealmaking]
#  ConsiderOnlineStorageDeals = true
#  ConsiderOfflineStorageDeals = true
#  ConsiderOnlineRetrievalDeals = true
#  ConsiderOfflineRetrievalDeals = true
#  PieceCidBlocklist = []
#  ExpectedSealDuration = "1m0s"
Filter = "{FILTER_PATH}"
#
[Sealing]
#  MaxWaitDealsSectors = 2
#  MaxSealingSectors = 0
#  MaxSealingSectorsForDeals = 0
#  WaitDealsDelay = "1m0s"
#
[Storage]
ParallelSealLimit = {SEAL_LIMIT}
ParallelFetchLimit = {FETCH_LIMIT}
LargeMemoryMode = true
FetchToShared = true
#  AllowAddPiece = false
#  AllowPreCommit1 = false
#  AllowPreCommit2 = false
#  AllowCommit = false
#  AllowUnseal = false
#
[Fees]
#  MaxPreCommitGasFee = "0.05 FIL"
#  MaxCommitGasFee = "0.05 FIL"
#  MaxWindowPoStGasFee = "50 FIL"
#
"""
    replace_file(os.path.join(DATA_PATH, f"lotusminer_{VERSION}/config.toml"), s)


def gen_run_miner():
    s = f"""#!/bin/bash
set -e

S=star
V={VERSION}

sleep 10

WORK_PATH=$(dirname $0)
$WORK_PATH/mount_hdd.sh

#echo 8222172 | sudo tee /proc/sys/kernel/threads-max
#echo 8388608 | sudo tee /proc/sys/vm/max_map_count
#echo 1000000 | sudo tee /proc/sys/kernel/pid_max
#echo 1000000 | sudo tee /sys/fs/cgroup/pids/user.slice/user-1000.slice/pids.max

export TRUST_PARAMS=1

export RUST_BACKTRACE=full
export RUST_LOG=info
export GOLOG_LOG_FMT=json
export BELLMAN_CUSTOM_GPU="GeForce RTX 3090:10496, GeForce RTX 3080:8704, GeForce RTX 3070:5888, GeForce RTX 3060:3584"

export LOTUS_PATH="/home/{USER}/share/ssd/data/lotus_$V"
export LOTUS_MINER_PATH="/home/{USER}/share/ssd/data/lotusminer_$V"

export IPFS_GATEWAY="https://filestar-proofs.s3.cn-east-1.jdcloud-oss.com/ipfs/"
export FIL_PROOFS_PARAMETER_CACHE="/home/{USER}/share/ssd/data/filecoin-proof-parameters"

export FIL_PROOFS_MAXIMIZE_CACHING=1
export SKIP_BASE_EXP_CACHE=1

mkdir -p /home/{USER}/share/ssd/bin/bin_$V
cp /home/{USER}/share/ssd/bin/bin_$S/lotus-miner /home/{USER}/share/ssd/bin/bin_$V/
/home/{USER}/share/ssd/bin/bin_$V/lotus-miner run &
sudo prlimit --nofile=1048576 --nproc=unlimited --rtprio=99 --nice=-19 --pid $!

wait
"""
    filename = os.path.join(SCRIPT_PATH, f'run_miner_{VERSION}.sh')
    replace_file(filename, s)
    time.sleep(1)
    subprocess.check_call(f"chmod +x {filename}", shell=True)


def update_miner_api():
    dest = os.path.join(DATA_PATH, 'lotusminer')
    if not os.path.exists(dest):
        os.mkdir(dest)
    subprocess.check_call(f"cp {os.path.join(DATA_PATH, 'lotusminer_{}/api'.format(VERSION))} {dest}", shell=True)
    subprocess.check_call(f"cp {os.path.join(DATA_PATH, 'lotusminer_{}/token'.format(VERSION))} {dest}", shell=True)


def set_miner_addrs():
    addrs = " ".join(PROXIES)
    cmd = f"lotus-miner actor set-addrs {addrs}"
    print(cmd)
    subprocess.check_call(cmd, shell=True)


def separate_wdpost_addr():
    addr = subprocess.check_output("lotus wallet new bls", universal_newlines=True, shell=True).strip()
    print("separate wdpost addr: ", addr)
    msgid = subprocess.check_output(f"lotus send {addr} 0.01", universal_newlines=True, shell=True).strip()

    def wait_msg():
        state = subprocess.check_output(f"lotus state search-msg {msgid}", universal_newlines=True, shell=True).strip()
        assert "message was executed in tipset" in state
    retry(wait_msg, max_times=9, interval=20)

    subprocess.check_call(f"lotus-miner actor control set --really-do-it {addr}", shell=True)        

def gen_mount_hdd():
    mounted_hdds = check_nfs()
    old = os.path.join(SCRIPT_PATH, "mount.sh")
    if os.path.exists(old):
        os.unlink(old)
    owd = os.getcwd()    
    os.chdir(f"/home/{USER}/share/ssd/script/fabric/fabric_storage")
    subprocess.check_call("fab shell", shell=True)
    with open(old, 'r') as f:
        text = f.read()
        s = f"""#!/bin/bash
R=()

{text}

for I in ${{R[@]}}
do
  wait $I
  J=$?
  [ $J -ne 0 ] && exit 1
done
exit 0
"""
        filename = os.path.join(SCRIPT_PATH, "mount_hdd.sh")
        replace_file(filename, s, False)
        subprocess.check_call(f"chmod +x {filename}", shell=True)
    check_mount_hdd_sh(mounted_hdds)
    os.chdir(owd)


def miner_superv_conf():
    s = f"""[program:miner_{VERSION}]
command=/home/{USER}/share/ssd/script/run_miner_{VERSION}.sh
user={USER}

autostart=true
autorestart=true
stopwaitsecs=60
startretries=100
stopasgroup=true
killasgroup=true
priority=991

redirect_stderr=true
stdout_logfile=/home/{USER}/share/hdd/log/miner_{VERSION}.log
stdout_logfile_maxbytes=512MB
stdout_logfile_backups=20
"""

    filename = "/etc/supervisor/conf.d/miner.conf"
    replace_file(filename, s)


def gen_run_worker():
    run_cmd = f"/home/{USER}/data/lotus-worker run --listen ${{IP}}:3456 --parallel-fetch-limit 8 >> /home/{USER}/share/hdd/log/worker.${{IP}}.log 2>&1 &"

    s = f"""#!/bin/bash
set -e

V={VERSION}
IP={LOCAL_IP}

[ $(mount -l | grep /home/{USER}/share | wc -l) -eq 1 ] || ( mkdir -p /home/{USER}/share && sudo mount -t nfs -o hard,intr,bg,nofail,noatime ${{IP}}:/home/{USER}/share /home/{USER}/share && sudo chown {USER}.{USER} /home/{USER}/share )

/home/{USER}/share/ssd/script/mount_hdd.sh

/home/{USER}/share/ssd/script/run_worker_$V.sh
    """

    filename = os.path.join(SCRIPT_PATH, "run_worker.sh")
    replace_file(filename, s)
    os.system(f"chmod +x {filename}")

    s = f"""#!/bin/bash
set -e

S=star

sleep 10

export RUST_BACKTRACE=full
export RUST_LOG=trace
export GOLOG_LOG_FMT=json
export BELLMAN_CUSTOM_GPU="GeForce RTX 3090:10496, GeForce RTX 3080:8704, GeForce RTX 3070:5888, GeForce RTX 3060:3584"

echo 53687091200 | sudo tee /proc/sys/vm/dirty_bytes
echo 10737418240 | sudo tee /proc/sys/vm/dirty_background_bytes
echo 1000 | sudo tee /proc/sys/vm/vfs_cache_pressure
echo 100 | sudo tee /proc/sys/vm/dirty_writeback_centisecs
echo 100 | sudo tee /proc/sys/vm/dirty_expire_centisecs
echo 100 | sudo tee /proc/sys/vm/watermark_scale_factor

#echo 8222172 | sudo tee /proc/sys/kernel/threads-max
#echo 8388608 | sudo tee /proc/sys/vm/max_map_count
#echo 1000000 | sudo tee /proc/sys/kernel/pid_max
#echo 1000000 | sudo tee /sys/fs/cgroup/pids/user.slice/user-1000.slice/pids.max

export LOTUS_PATH="/home/{USER}/share/ssd/data/lotus"
export LOTUS_MINER_PATH="/home/{USER}/share/ssd/data/lotusminer"
export WORKER_PATH="{WORKER_PATH}"

export IPFS_GATEWAY="https://do.u.forget.io/fabparam"
export FIL_PROOFS_PARAMETER_CACHE="{WORKER_PROOFS_PARAMETER_PATH}"

export FIL_PROOFS_MAXIMIZE_CACHING=1
unset USE_EXP_CACHE
{"export FIL_PROOFS_USE_GPU_COLUMN_BUILDER=1" if WORKER_USE_GPU else "unset FIL_PROOFS_USE_GPU_COLUMN_BUILDER"}
{"export FIL_PROOFS_USE_GPU_TREE_BUILDER=1" if WORKER_USE_GPU else "unset FIL_PROOFS_USE_GPU_TREE_BUILDER"}

IP=`hostname -I | awk '{{print $1}}'`

{"nvidia-smi" if WORKER_USE_GPU else ""}
{"if [ $? -ne 0 ]; then" if WORKER_USE_GPU else ""}
{'  echo "ERROR: no GPU detected $IP"' if WORKER_USE_GPU else ""}
{"  exit" if WORKER_USE_GPU else ""}
{"fi" if WORKER_USE_GPU else ""}

mkdir -p /home/{USER}/data
cp /home/{USER}/share/ssd/bin/bin_$S/lotus-worker /home/{USER}/data/
{run_cmd}
sudo prlimit --nofile=1048576 --nproc=unlimited --rtprio=99 --nice=-19 --pid $!

wait
    """

    filename = os.path.join(SCRIPT_PATH, f"run_worker_{VERSION}.sh")
    replace_file(filename, s)
    os.system(f"chmod +x {filename}")


def gen_worker_conf():
    s = f"""[program:worker]
command=/home/{USER}/data/run_worker.sh
user={USER}

autostart=true
autorestart=true
stopwaitsecs=60
startretries=999
stopasgroup=true
killasgroup=true

redirect_stderr=true
stdout_logfile=/home/{USER}/worker.log
stdout_logfile_maxbytes=256MB
    """
    dest = f'/home/{USER}/share/ssd/conf/'
    if not os.path.exists(dest):
        os.mkdir(dest)
    replace_file(os.path.join(dest, "worker.conf"), s)


def auto_deploy_lotus():
    lotus_path = f"/home/{USER}/share/ssd/data/lotus_{VERSION}/keystore"
    if os.path.exists(lotus_path):
        answer = input("lotus seems already deployed, are you sure to override ? (y or n):")
        if not answer.lower().startswith("y"):
            return

    subprocess.check_call("sudo supervisorctl stop all", shell=True)
    subprocess.check_call("rm -rf /mnt/*.*.*.*/disk*/lotus*", shell=True)

    if not os.path.exists(f"/home/{USER}/share/hdd/"):
        subprocess.check_call(f"mkdir /home/{USER}/share/hdd", shell=True)

    if not os.path.exists(f"/home/{USER}/share/hdd/log/"):
        subprocess.check_call(f"mkdir /home/{USER}/share/hdd/log", shell=True)

    gen_run_lotus()
    os.chdir(SCRIPT_PATH)
    subprocess.check_call("sudo python3 ./deploy.py lotus-superv-conf", shell=True)
    subprocess.check_call(f"sudo supervisorctl update lotus_{VERSION}", shell=True)
    time.sleep(2)
    status = subprocess.check_output(f"sudo supervisorctl status|grep lotus_{VERSION}", universal_newlines=True, shell=True)
    if "STOPPED" in status:
        subprocess.check_call(f"sudo supervisorctl start lotus_{VERSION}", shell=True)
    time.sleep(15)
    retry(update_lotus_config, max_times=60, interval=20)
    subprocess.check_call(f"sudo supervisorctl restart lotus_{VERSION}", shell=True)
    time.sleep(10)
    retry(update_lotus_api, max_times=60, interval=20)
    priv = input("import private key (leave this empty to create new):").strip()
    if priv:
        output = subprocess.check_output(f"echo \"{priv}\" | lotus wallet import", universal_newlines=True, shell=True)
        owner = output.split(" ")[-2].strip()
    else:
        owner = subprocess.check_output("lotus wallet new bls", universal_newlines=True, shell=True)
    subprocess.check_call(f"lotus wallet set-default {owner}", shell=True)
    print("\nauto deploy lotus done, please manually send some FIL to", owner)


def auto_deploy_miner():
    check_gethost()
    if not os.path.exists(os.path.join(DATA_PATH, f"lotusminer_{VERSION}")):
        gen_init_miner()
        balance = subprocess.check_output("lotus wallet balance", universal_newlines=True, shell=True)
        if "warning" in balance:
            print("invalid balance", balance)
            return
        balance = float(balance.split(" ")[0])
        if balance < 0.1:
            print("balance too small, need at least 0.1 FIL")
            return    
        os.chdir(SCRIPT_PATH)
        subprocess.check_call(f"./init_miner_{VERSION}.sh", shell=True)
    if not os.path.exists(FILTER_PATH):
        gen_default_filter()
    update_miner_config()
    gen_mount_hdd()
    gen_run_miner()
    os.chdir(SCRIPT_PATH)
    subprocess.check_call("sudo python3 ./deploy.py miner-superv-conf", shell=True)
    subprocess.check_call(f"sudo supervisorctl update miner_{VERSION}", shell=True)
    time.sleep(2)
    status = subprocess.check_output(f"sudo supervisorctl status|grep miner_{VERSION}", universal_newlines=True, shell=True)
    if "STOPPED" in status:
        subprocess.check_call(f"sudo supervisorctl start miner_{VERSION}", shell=True)
    time.sleep(30)
    retry(update_miner_api, max_times=60, interval=20)
    os.chdir(os.path.join(SCRIPT_PATH, "fabric/fabric_storage/"))
    subprocess.check_call(f"sed -i 's/storage = .*/storage = \"lotusminer_{VERSION}\"/' fabfile.py", shell=True)
    subprocess.check_call("fab attach", shell=True)
    check_attach()
    separate_wdpost_addr()
    output = subprocess.check_output('lotus-miner info | grep "Miner:"', universal_newlines=True, shell=True)
    miner = output.replace("Miner:", "").strip()
    if (not miner.startswith("f")) and (not miner.startswith("t")):
        raise Exception(f"failed get miner id, got: {output}")
    subprocess.check_call("lotus-miner storage-deals set-ask --price 1 --verified-price 1 --min-piece-size 128MiB --max-piece-size 32GiB", shell=True)
    print("\nauto deploy miner done: ", miner)


def auto_deploy_worker():
    with open(os.path.join(SCRIPT_PATH, "fabric/computing.lst"), 'r') as f:
        for worker in f:
            worker = worker.strip()
            if worker.startswith("#"):
                continue
            if worker == LOCAL_IP:
                raise Exception("found host ip in computing.lst")
    check_param()
    gen_run_worker()
    gen_worker_conf()
    os.chdir(os.path.join(SCRIPT_PATH, "fabric/fabric_worker"))
    subprocess.check_call("fab worker_remove", shell=True)
    subprocess.check_call("fab worker_init", shell=True)
    print("\nauto deploy worker done")


def check_nfs() -> dict:
    record = defaultdict(list)
    output = subprocess.check_output('df -H | grep -P "([0-9]{1,3}[.]){3}[0-9]{1,3}"', universal_newlines=True, shell=True)
    for line in output.split("\n"):
        line = line.split(" ")[0].strip()
        if ":" not in line:
            continue
        if "/home/ps/share" in line:
            continue
        ip, path = line.split(":")
        index = path.split("/")[-1].replace("disk", "")
        if not index.isdigit():
            raise Exception(f"found wrong path for {ip} : {index}")
        record[ip].append(int(index))
    for ip, paths in record.items():
        paths = sorted(paths)
        start = paths[0]
        end = paths[-1]
        if len(paths) != (end + 1 - start):
            raise Exception(f"missing path for {ip} : {paths}")
        print(f"mounted {len(paths)} disks for {ip}, check passed")    
    return record

def export_nfs():
    record = set()
    output = subprocess.check_output('df -H | grep -P "([0-9]{1,3}[.]){3}[0-9]{1,3}"', universal_newlines=True, shell=True)
    for line in output.split("\n"):
        line = line.split(" ")[0].strip()
        if ":" not in line:
            continue
        if "/home/ps/share" in line:
            continue
        ip, path = line.split(":")
        index = path.split("/")[-1].replace("disk", "")
        if not index.isdigit():
            raise Exception(f"found wrong path for {ip} : {index}")
        record.add(ip)
    for ip in sorted(record):
        print(ip)


def df_nfs():
    output = subprocess.check_output('df -H | grep -P "([0-9]{1,3}[.]){3}[0-9]{1,3}"', universal_newlines=True, shell=True)
    for line in output.split("\n"):
        path = line.split(" ")[-1].strip()
        if ":" not in line:
            continue
        if "/home/ps/share" in line:
            continue
        try:
            subprocess.check_call(f"df {path}", shell=True)
        except BaseException as e:
            print(f"error df {path}, {e}")
            continue


def check_attach():
    mounted_hdds = check_nfs()
    record = defaultdict(list)
    with open(f"/home/{USER}/share/ssd/data/lotusminer_{VERSION}/storage.json", 'r') as f:
        data = json.load(f)
        for path in data['StoragePaths']:
            p = path['Path'].split("/")
            ip = p[-3]
            index = p[-2].replace("disk", "")
            if not index.isdigit():
                print(f"found wrong path for {ip} : {index}")
                raise Exception("attach check failed")
            record[ip].append(int(index))
    if not len(record.keys()) == len(mounted_hdds.keys()):
        raise Exception("mount_hdd.sh hosts don't match with local mounted hdds")
    good = True
    for ip, attachs in record.items():
        mouteds = mounted_hdds[ip]
        attachs = sorted(attachs)
        mouteds = sorted(mouteds)
        if attachs != mouteds:
            good = False
            print(f"path mismatch for {ip}, attached: {attachs}, expected: {mouteds}")
    if good:
        print("attach check passed")
    else:
        raise Exception("attach check failed")


def check_mount_hdd_sh(mounted_hdds=None):
    if not mounted_hdds:
        mounted_hdds = check_nfs()
    record = defaultdict(list)
    filename = os.path.join(SCRIPT_PATH, "mount_hdd.sh")
    with open(filename, 'r') as f:
        for line in f:
            if not line.startswith("""{ [ $(mount -l | grep"""):
                continue
            path_re = re.compile('sudo mkdir -p (.*?) && ')
            path = path_re.findall(line)
            if not len(path) == 1:
                raise Exception(f"path not found in {filename} : {line}")
            path = path[0]
            ip = path.split("/")[-2]
            index = path.split("/")[-1].replace("disk", "")
            if not index.isdigit():
                raise Exception(f"found wrong path in {filename} : {line}")
            record[ip].append(int(index))
    if not len(record.keys()) == len(mounted_hdds.keys()):
        raise Exception("mount_hdd.sh hosts don't match with local mounted hdds, nfs: {}, generated: {}".format(record.keys(), mounted_hdds.keys()))
    good = True
    for ip, attachs in record.items():
        mouteds = mounted_hdds[ip]
        attachs = sorted(attachs)
        mouteds = sorted(mouteds)
        if attachs != mouteds:
            good = False
            print(f"path mismatch for {ip}, attached: {attachs}, expected: {mouteds}")
    if good:
        print("mount_hdd.sh check passed")
    else:
        raise Exception("mount_hdd.sh check failed")


def check_gethost():
    for dir in ("fabric_storage", "fabric_worker"):
        with open(os.path.join(SCRIPT_PATH, f"fabric/{dir}/fabfile.py"), "r") as f:
            begin = False
            for line in f:
                if "hosts.extend" in line:
                    begin = True
                    continue
                if not begin:
                    continue
                if "#" in line:
                    continue
                if "return" in line:
                    break
                if "hosts =" in line or "hosts=" in line:
                    raise Exception(f"found hosts override in {dir}/fabfile.py : {line}")
    print("check_gethost passed")


def check_worker():
    missing_workers = set()
    with open(os.path.join(SCRIPT_PATH, f"fabric/computing.lst"), "r") as f:
        for line in f:
            ip = line.strip()
            if not ip or "#" in ip:
                continue
            missing_workers.add(ip)
    online_workers = set()
    disabled_workers = set()
    output = subprocess.check_output('lotus-miner sealing workers | grep -P "host ([0-9]{1,3}[.]){3}[0-9]{1,3}"', universal_newlines=True, shell=True)
    for line in output.split("\n"):
        if not line.strip():
            continue
        disabled = "disabled" in line
        ip = line.replace(" (disabled)", "").split(" ")[-1].split(":")[0].strip()
        if not ip:
            continue
        if disabled:
            disabled_workers.add(ip)
            missing_workers.remove(ip)
        else:
            online_workers.add(ip)
            missing_workers.remove(ip)
    if len(missing_workers) > 0:
        print("found missing wokers:", list(sorted(missing_workers)))
    if len(disabled_workers) > 0:
        print("found disabled wokers:", list(sorted(disabled_workers)))
    print(f"found {len(online_workers)} workers online")


def check_job():
    duration_alert = {
        "PC2": timedelta(hours=1),
        "C1": timedelta(hours=0.5),
        "C2": timedelta(hours=1.5),
    }
    if SECTOR_SIZE == 64:
        duration_alert["PC1"] = timedelta(hours=8)
    if SECTOR_SIZE == 32:
        duration_alert["PC1"] = timedelta(hours=6)
    if SECTOR_SIZE == 8:
        duration_alert["PC1"] = timedelta(hours=3)

    output = subprocess.check_output('lotus-miner sealing jobs | grep -P "([0-9]{1,3}[.]){3}[0-9]{1,3}:"', universal_newlines=True, shell=True)
    for line in output.split("\n"):
        if not line.strip():
            continue
        data = line.split("  ")
        sector = data[1]
        worker = data[4]
        job = data[5]
        if job not in duration_alert:
            continue    
        duration = data[-1]
        if "ms" in duration:
            continue
        duration = parse_time(duration)
        if duration > duration_alert[job]:
            print(f"{worker} {job} {sector} takes too long: {duration}")


def check_param():
    owd = os.getcwd()
    fab_path = os.path.join(SCRIPT_PATH, "fabric/fabric_worker/")
    file_path = os.path.join(fab_path, "fabfile.py")
    defined = False
    print("file_path", file_path)
    text = subprocess.check_output(f"cat {file_path}", universal_newlines=True, shell=True)
    defined = "ls_param()" in text
    if not defined:
        code = f"""

@parallel
def ls_param():
    run('ls {WORKER_PROOFS_PARAMETER_PATH}|wc -l')

"""
        subprocess.check_call(f'echo "{code}" >> {file_path}', shell=True)
    os.chdir(fab_path)
    subprocess.call("fab ls_param", shell=True)
    is_continue = input("accept above param count? (y or n):").lower().strip().startswith("y")
    os.chdir(owd)
    if not is_continue:
        exit(1)

def gen_config():
    try:
        local_ip = subprocess.check_output("hostname -I",universal_newlines=True, shell=True).strip()
    except:
        local_ip = input("local ip:").strip()
    assert(local_ip)

    sector_size = int(input("sector-size (64、32 or 8):").strip())
    if sector_size not in [64, 32, 8]:
        raise Exception(f"invalid sector size {sector_size}")

    default_seal_limits = {
        8: 28,
        32: 28,
        64: 11
    }

    default_fetch_limits = {
        8: 400,
        32: 100,
        64: 50
    }

    conf = {
        "local_ip": local_ip,
        "extern_ips": [],
        "lotus_api_listen": 1819,
        "lotus_p2p_listen": 0,
        "miner_p2p_listen": 0,
        "miner_p2p_announce": 0,
        "version": "v0",
        "use_gpu": True,
        "user": "ps",
        "seal_limit": default_seal_limits[sector_size],
        "fetch_limit": default_fetch_limits[sector_size],
        "sector_size": sector_size,
    }
    replace_file("deploy.conf", json.dumps(conf, indent=4))


if __name__ == "__main__":
    argv = sys.argv[1:]
    assert(len(argv) == 1)
    cmd = argv[0]

    if not os.path.exists("deploy.conf"):
        gen_config()
        if cmd == "gen-config":
            exit(0)

    conf = None
    with open("deploy.conf", "r") as f:
        conf = json.load(f)

    LOCAL_IP = conf["local_ip"]
    VERSION = conf["version"]
    WORKER_USE_GPU = conf["use_gpu"]
    USER = conf["user"]
    LOTUS_API_LISTEN = conf["lotus_api_listen"]
    LOTUS_P2P_LISTEN = conf["lotus_p2p_listen"]
    MINER_P2P_LISTEN = conf["miner_p2p_listen"]
    MINER_P2P_ANNOUNCE = conf["miner_p2p_announce"]
    SEAL_LIMIT = conf["seal_limit"]
    FETCH_LIMIT = conf["fetch_limit"]
    SECTOR_SIZE = conf.get("sector_size", 32)
    
    EXTERN_IPS = conf["extern_ips"]
    PROXIES = []
    ip_re = re.compile('^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$')
    for addr in EXTERN_IPS:
        if ip_re.match(addr):
            PROXIES.append(f"/ip4/{addr}/tcp/{MINER_P2P_ANNOUNCE}")
        else:
            PROXIES.append(f"/dns4/{addr}/tcp/{MINER_P2P_ANNOUNCE}")

    DATA_PATH = f'/home/{USER}/share/ssd/data'
    SCRIPT_PATH = f'/home/{USER}/share/ssd/script'
    WORKER_PATH = "/mnt/md0/lotusworker"
    WORKER_PROOFS_PARAMETER_PATH = "/mnt/md0/filecoin-proof-parameters"
    FILTER_PATH = f"/home/{USER}/share/ssd/script/dealfilter.pl"
    BIN_PATH = f'/home/{USER}/share/ssd/bin'

    uid = getpwnam(USER)[2]
    if uid != 1000:
        goon = input(f"the uid is {uid}, are you sure to continue (y or n):").strip()
        if not goon.lower().startswith('y'):
            exit(0)

    cmds = {
        "gen-config": gen_config,
        "gen-run-lotus": gen_run_lotus,
        "lotus-superv-conf": lotus_superv_conf,
        "update-lotus-config": update_lotus_config,
        "update-lotus-api": update_lotus_api,
        "gen-init-miner": gen_init_miner,
        "gen-default-filter": gen_default_filter,
        "update-miner-config": update_miner_config,
        "gen-mount-hdd": gen_mount_hdd,
        "gen-run-miner": gen_run_miner,
        "miner-superv-conf": miner_superv_conf,
        "update-miner-api": update_miner_api,
        "set-miner-addrs": set_miner_addrs,
        "separate-wdpost-addr": separate_wdpost_addr,
        "gen-run-worker": gen_run_worker,
        "gen-worker-conf": gen_worker_conf,
        "auto-deploy-lotus": auto_deploy_lotus,
        "auto-deploy-miner": auto_deploy_miner,
        "auto-deploy-worker": auto_deploy_worker,
        "check-nfs": check_nfs,
        "export-nfs": export_nfs,
        "df-nfs": df_nfs,
        "check-attach": check_attach,
        "check-mount-hdd-sh": check_mount_hdd_sh,
        "check-gethost": check_gethost,
        "check-worker": check_worker,
        "check-job": check_job,
        "check-param": check_param,
    }

    if cmd in cmds:
        cmds[cmd]()
    else:
        print("invalid command, should be one of:", list(cmds.keys()))

