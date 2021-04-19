import json
import logging

from fabric.api import env, run, sudo, reboot, settings, parallel, local, put

logging.basicConfig(level=logging.INFO)

env.user = 'ps'
env.password = raw_input('Enter Password:')


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


def get_hosts():
    hosts = []
    hosts.extend(get_part(part_name='storage'))
    # hosts.extend(get_part(part_name='computing'))
    # hosts = hosts[:1]
    logging.info("%s %s" % (hosts, len(hosts)))
    return hosts


env.hosts = get_hosts()


@parallel
def hello():
    run('df -H')


@parallel
def restart():
    with settings(warn_only=True):
        reboot(600)


@parallel
def install():
    sudo("apt update")
    sudo('apt -y upgrade')
    sudo("apt install -y ubuntu-drivers-common ntpdate iperf tree nfs-kernel-server")
    sudo('ubuntu-drivers autoinstall')
    sudo('apt autoremove')


def improve():
    sudo('sed -i "s/RPCNFSDCOUNT=.*/RPCNFSDCOUNT=24/g" /etc/default/nfs-kernel-server')
    sudo('echo 1048576 > /proc/sys/net/core/wmem_default')
    sudo('echo 1048576 > /proc/sys/net/core/wmem_max')
    sudo('echo 1048576 > /proc/sys/net/core/rmem_default')
    sudo('echo 1048576 > /proc/sys/net/core/rmem_max')
    sudo('service nfs-kernel-server restart')


@parallel
def time_adjust():
    sudo('ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime')
    sudo('ntpdate ntp.aliyun.com')


@parallel
def firm():
    put("/home/ps/share/hdd/data/intelmas_1.1.884-0_amd64.deb", "/home/ps")
    sudo('dpkg -i /home/ps/intelmas_1.1.884-0_amd64.deb')

    with settings(warn_only=True):
        for i in range(5):
            sudo('intelmas load -f -intelssd %s' % i)

    run('rm -f /home/ps/intelmas_1.1.884-0_amd64.deb')


@parallel(1)
def iperf():
    # ip = local('hostname -I', capture=True).split(' ')[1]
    ip = local('hostname -I', capture=True)
    run('iperf -t 1 -c %s' % ip)


@parallel
def clear():
    sudo('sed -i "/mnt\/disk/d" /etc/fstab')
    sudo('sed -i "/#/!d" /etc/exports')


@parallel
def mkfs():
    disks = sudo('lsblk -p -J')
    disks = json.loads(disks)

    paths = []
    for disk in disks["blockdevices"]:
        if 'T' not in disk['size']:
            continue
        if disk["name"][0:7] != '/dev/sd':
            continue

        paths.append(disk["name"])

    for path in paths:
        with settings(warn_only=True):
            sudo('umount ' + path)

    for path in paths:
        sudo('mkfs.xfs -f ' + path)


@parallel
def mount():
    sudo('sed -i "/mnt\/disk/d" /etc/fstab')

    i = 1
    disks = sudo('lsblk -f -p -J')
    disks = json.loads(disks)

    for disk in disks["blockdevices"]:
        if disk['fstype'] != 'xfs':
            continue
        if disk["name"][0:7] != '/dev/sd':
            continue

        uuid = disk["uuid"]
        sudo('mkdir -p /mnt/disk%s' % i)
        with settings(warn_only=True):
            sudo('umount /mnt/disk%s' % i)
        sudo('mount /dev/disk/by-uuid/%s /mnt/disk%s' % (uuid, i))
        sudo('chown ps.ps /mnt/disk%s' % i)
        sudo('umount /mnt/disk%s' % i)

        uuid = run('uuidgen')
        sudo('xfs_admin -U %s %s' % (uuid, disk["name"]))

        sudo('sed -i "/%s/d" /etc/fstab' % uuid)
        sudo('echo "/dev/disk/by-uuid/%s /mnt/disk%s xfs noatime 0 0" >> /etc/fstab' % (uuid, i))

        i += 1


def mount_res():
    run('df -H')
    run('cat /etc/fstab')
    run('cat /etc/default/nfs-kernel-server | head')


def export():
    sudo('sed -i "/#/!d" /etc/exports')

    disks = sudo('df -H | grep /dev/sd | grep T')
    for line in disks.split('\n'):
        line = line.strip().split(' ')
        path = line[-1]
        sudo('echo "%s 172.18.0.0/16(rw,no_root_squash,no_subtree_check,async)" >> /etc/exports' % path)

    sudo('exportfs -a')
    sudo('service portmap restart')
    sudo('service nfs-mountd restart')
    sudo('service nfs-server restart')


def client():
    ip = run('hostname -I')

    disks = sudo('df -H | grep /dev/sd | grep T | sort')
    for line in disks.split('\n'):
        line = line.strip().split(' ')
        path = line[-1][5:]
        local('sudo mkdir -p /mnt/%s/%s' % (ip, path))
        with settings(warn_only=True):
            local('sudo umount /mnt/%s/%s' % (ip, path))
            local('sudo mount -t nfs -o noatime %s:/mnt/%s /mnt/%s/%s' % (ip, path, ip, path))
        local('sudo chown ps.ps /mnt/%s/%s' % (ip, path))


def shell():
    ip = run('hostname -I')
    disks = sudo('df -H | grep /dev/sd | grep T | sort')
    for line in disks.split('\n'):
        line = line.strip().split(' ')
        path = line[-1]
        path = path.split('/')
        extra_part = ''
        if len(path) == 4:
            extra_part = '/' + path[-2]
        path = path[-1]

        cmd_list = []
        cmd_list.append('sudo mkdir -p /mnt%s/%s/%s' % (extra_part, ip, path))
        cmd_list.append(
            'sudo mount -t nfs -o noatime %s:/mnt%s/%s /mnt%s/%s/%s' % (ip, extra_part, path, extra_part, ip, path))
        cmd_list.append('sudo chown ps.ps /mnt%s/%s/%s' % (extra_part, ip, path))

        pre_cmd = '[ $(mount -l | grep " /mnt%s/%s/%s " | wc -l) -eq 1 ]' % (extra_part, ip, path)
        after_cmd = '(%s)' % ' && '.join(cmd_list)
        cmd = '{ %s || %s } &' % (pre_cmd, after_cmd)

        local("echo '%s' >> /home/ps/share/ssd/script/mount.sh" % cmd)
        local("echo 'R[${#R[@]}]=$!' >> /home/ps/share/ssd/script/mount.sh")

    local("echo '' >> /home/ps/share/ssd/script/mount.sh")


def attach():
    version = local('sudo supervisorctl status | grep miner', capture=True).split(' ')[0]
    version = version.split('_')[1]
    storage = "lotusminer_%s" % version
    hostname = run('hostname -I')
    paths = local('ls /mnt/%s' % hostname, capture=True).strip().split('\n')
    for path in paths:
        if "efi" in path:
            raise Exception("found efi in /mnt/{}/{}".format(hostname, path))
        local('sudo chown ps.ps /mnt/%s/%s' % (hostname, path))
        local('lotus-miner storage attach /mnt/%s/%s/%s' % (hostname, path, storage))


@parallel
def add_ssh_key():
    ssh_key = local('cat /home/ps/.ssh/id_rsa.pub', capture=True)
    run('mkdir -p /home/ps/.ssh')
    run('touch /home/ps/.ssh/authorized_keys')
    run('sed -i "/filecoin-main/d" /home/ps/.ssh/authorized_keys')
    run('echo "%s" >> /home/ps/.ssh/authorized_keys' % ssh_key)


@parallel
def time_adjust():
    sudo('ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime')
    sudo('ntpdate -t 5 ntp.aliyun.com')


@parallel(1)
def lsblk():
    run('lsblk | grep T')


@parallel
def connect_disks():
    put("~/m.deb", "~/")
    sudo('apt update')
    sudo('apt-get install lib32ncurses5-dev -y')
    sudo('dpkg -i ~/m.deb')
    sudo('/opt/MegaRAID/MegaCli/MegaCli64 -CfgForeign -Scan -aALL')
    sudo('/opt/MegaRAID/MegaCli/MegaCli64 -cfgclr  -a0')
    sudo('/opt/MegaRAID/MegaCli/MegaCli64  -cfgforeign -clear -a0')
    sudo('/opt/MegaRAID/MegaCli/MegaCli64 -AdpSetProp -EnableJBOD -1  -a0')


@parallel
def iperf_receiving():
    run('iperf -s')


@parallel
def one_key():
    install()
    add_ssh_key()
    time_adjust()
    firm()
    iperf()
    restart()
    mkfs()
    mount()
    mount_res()
    restart()
    export()
    improve()
    client()
