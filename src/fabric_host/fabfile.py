import logging

from fabric.api import env, run, settings, parallel, local

logging.basicConfig(level=logging.ERROR)

env.user = 'ps'
env.password = raw_input('Enter Password:')
env.hosts = ['127.0.0.1']


def get_part(part_name='rw_storage', size=1000, direction=True):
    hosts = []
    with open('../%s.lst' % part_name) as f:
        for line in f:
            if line[0] == "#":
                continue

            line = line.strip()
            if len(line) == 0:
                continue
            hosts.append(line)
    if len(hosts) > size:
        if direction:
            hosts = hosts[:size]
        else:
            hosts = hosts[size:]
    return hosts


def restart():
    with settings(warn_only=True, prompts=env.password):
        local('sudo reboot')


def apt_source():
    s = """deb http://mirrors.aliyun.com/ubuntu/ bionic main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ bionic-security main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ bionic-updates main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ bionic-proposed main restricted universe multiverse
deb http://mirrors.aliyun.com/ubuntu/ bionic-backports main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ bionic main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ bionic-security main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ bionic-updates main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ bionic-proposed main restricted universe multiverse
deb-src http://mirrors.aliyun.com/ubuntu/ bionic-backports main restricted universe multiverse
    """
    apt = local("sudo cat /etc/apt/sources.list", capture=True)
    if "aliyun" not in apt:
        with open("/etc/apt/sources.list", 'w') as f:
            f.write(str(s))


def install():
    local("sudo apt update")
    local('sudo apt -y upgrade')
    local(
        "sudo apt install -y mesa-opencl-icd ocl-icd-opencl-dev libhwloc-dev ntpdate ubuntu-drivers-common nfs-kernel-server supervisor miniupnpc iperf tree unzip fabric python-requests iftop nload jq")
    local("sudo update-pciids")
    nvidia_install()
    local('sudo apt -y autoremove')
    local('sudo apt -y purge')


@parallel
def nvidia_remove():
    local('sudo apt-get --purge remove -y nvidia-*')
    local('sudo apt-get --purge remove -y libnvidia-*')
    local('sudo apt-get remove --purge nvidia-\*')
    local('sudo apt-get purge nvidia*')
    local('sudo apt autoremove --purge -y')

    local('sudo apt -y autoremove')
    local('sudo apt -y purge')
    local('sudo rmmod nvidia-drm')
    local('sudo rmmod nvidia-modeset')
    local('sudo rmmod nvidia_uvm')
    local('sudo rmmod nvidia')
    local('sudo rm -rf /lib/modules/`uname -r`/kernel/nvidia-460')
    local('sudo rm -rf /lib/modules/`uname -r`/updates/dkms/nvidia*')


@parallel
def nvidia_cp_drive(nvidia_info=None):
    drive_name = 'NVIDIA-Linux-x86_64-'
    if not nvidia_info:
        nvidia_info = local("sudo  lspci | grep -i nvidia").split('\n')[0]
    if "30" in nvidia_info or '220' in nvidia_info:
        drive_name += '460.39.run'
    else:
        drive_name += '450.102.04.run'
    return drive_name


@parallel
def nvidia_install():
    nvidia_info = local("sudo lspci | grep -i nvidia").split('\n')[0]
    with settings(warn_only=True):
        nvidia_remove()
        drive_name = nvidia_cp_drive(nvidia_info)
        local("sudo chmod a+x %s" % drive_name)
    local("sudo /home/ps/share/hdd/nvidia/%s --ui=none --no-questions" % drive_name)


def rm_auto_upgrade():
    with settings(warn_only=True):
        local('sudo rm /etc/apt/apt.conf.d/20auto-upgrades')


def time_adjust():
    local('sudo ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime')
    local('sudo ntpdate -t 5 ntp.aliyun.com')


def thread():
    local("sudo bash /home/ps/share/hhd/script/hyper-thread.sh && sleep 1")


def ast():
    local("sudo gzip -dk /home/ps/share/hdd/data/ast_dp501_fw.bin.gz")
    local("sudo mv /home/ps/share/hdd/data/ast_dp501_fw.bin /lib/firmware/")


def firm():
    local('sudo dpkg -i /home/ps/share/hdd/data/intelmas_1.1.884-0_amd64.deb')

    with settings(warn_only=True):
        for i in range(7):
            local('sudo intelmas load -f -intelssd %s' % i)


def firm_show():
    local('sudo intelmas show -intelssd')


def check_gpu_status():
    local('nvidia-smi -L')


def mkfs():
    raid = local('cat /proc/mdstat |grep md', capture=True)
    raid = raid.split(' ')[0]
    if "md" in raid:
        local("sudo mdadm --stop /dev/%s" % raid)


def mount():
    hdd = local('lsblk | grep T | grep nvme', capture=True)
    hdd = hdd.split(' ')[0]
    device = '/dev/' + hdd
    local('sudo mkfs.xfs -f %s' % device)
    local('sudo mkdir -p  /home/ps/share')
    local('sudo mount %s  /home/ps/share' % device)
    local('sudo chown -R ps.ps /home/ps/share')
    uuid = local('sudo blkid |grep %s' % hdd, capture=True)
    uuid = uuid.split(' ')[1]
    with settings(warn_only=True):
        local('echo %s /home/ps/share xfs noatime 0 0 |sudo tee -a /etc/fstab' % uuid)
        local('echo "/home/ps/share 172.18.0.0/16(rw,no_root_squash,no_subtree_check,async)" |sudo tee -a /etc/exports')
        local('sudo exportfs -a')
        local('sudo service portmap restart')
        local('sudo service nfs-server restart')


def filestar_source():
    s = '''export RUST_BACKTRACE=full
export RUSTFLAGS="-C target-cpu=native -g"
export FFI_BUILD_FROM_SOURCE=1
export RUST_LOG=trace

export LOTUS_PATH="/home/ps/share/ssd/data/lotus"
export LOTUS_MINER_PATH="/home/ps/share/ssd/data/lotusminer"
export WORKER_PATH="/home/ps/share/ssd/data/lotusworker"

export IPFS_GATEWAY="https://filestar-proofs.s3.cn-east-1.jdcloud-oss.com/ipfs/"
export FIL_PROOFS_PARAMETER_CACHE="/home/ps/share/ssd/data/filecoin-proof-parameters"
'''
    with open("/home/ps/.lotusprofile", 'w') as f:
        f.write(str(s))
    local('echo . "$HOME/.lotusprofile" >> ~/.profile')


def filecoin_source():
    s = '''export RUST_BACKTRACE=full
export RUSTFLAGS="-C target-cpu=native -g"
export FFI_BUILD_FROM_SOURCE=1
export RUST_LOG=trace

export LOTUS_PATH="/home/ps/share/ssd/data/lotus"
export LOTUS_MINER_PATH="/home/ps/share/ssd/data/lotusminer"
export WORKER_PATH="/home/ps/share/ssd/data/lotusworker"

export IPFS_GATEWAY="https://proof-parameters.s3.cn-south-1.jdcloud-oss.com/ipfs/"
export FIL_PROOFS_PARAMETER_CACHE="/home/ps/share/ssd/data/filecoin-proof-parameters"
'''
    with open("/home/ps/.lotusprofile", 'w') as f:
        f.write(str(s))
    local('echo . "$HOME/.lotusprofile" >> ~/.profile')


def check_env():
    path = local('echo $LOTUS_PATH')
    if "lotus" not in path:
        print("env set bad")
    mount = local('df -H')
    if "share" not in mount:
        print("share not mount")


def iperf():
    ip = local('hostname -I', capture=True)
    run('iperf -t 1 -c %s' % ip)


@parallel(1)
def iperf_to_storage():
    storages = []
    storages.extend(get_part(part_name='storage'))
    for ip in storages:
        local('iperf -t 1 -c %s' % ip, capture=True)

def set_hostname():
    ip = run("hostname -I")
    newhostname = ip.replace(".", "-")
    oldhostname = run("hostname")
    sudo('hostnamectl set-hostname %s' % newhostname)
    sudo('sed -i "s/%s/%s/g" /etc/hosts' % (oldhostname, newhostname))


@parallel
def create_user_ps():
    with settings(warn_only=True):
        sudo("groupadd -g 1999 ps")
        sudo("useradd -d /home/ps -m -s /bin/bash -g ps -G sudo -u 1999 ps")
        sudo('echo "ps:6block" |chpasswd')


def zap():
    local("sudo mv /home/ps/share/hdd/data/zap-pretty /usr/local/bin/")

@parallel
def one_key():
    apt_source()
    install()
    rm_auto_upgrade()
    time_adjust()
    thread()
    firm()
    ast()
    mkfs()
    mount()
    hostname = local('hostname', capture=True)
    if 'star' in hostname:
        filestar_source()
    else:
        filecoin_source()
    restart()
