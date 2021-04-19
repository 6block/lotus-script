import json
import logging
import random

from fabric.api import env, run, sudo, reboot, settings, parallel, local, put

logging.basicConfig(level=logging.INFO)

env.user = 'ps'
env.password = raw_input('Enter Password:')


def get_part(part_name='computing', size=1000, direction=True):
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
    hosts.extend(get_part(part_name='computing'))
    # hosts.extend(get_part(part_name='computing'))
    # hosts = hosts[:1]
    logging.info("%s %s" % (hosts, len(hosts)))
    return hosts


env.hosts = get_hosts()


@parallel
def hello():
    run('df -H')


@parallel
def ssd_raid_size():
    run('df -h /mnt/md0/')


@parallel
def restart():
    with settings(warn_only=True):
        reboot(600)


@parallel(1)
def check_worker():
    run('ps -ef | grep lotus')


@parallel
def install():
    sudo("apt update")
    sudo('apt -y upgrade')
    sudo(
        "apt install -y mdadm ubuntu-drivers-common ntpdate iperf tree mesa-opencl-icd ocl-icd-opencl-dev nfs-common supervisor nvme-cli")
    r = run('nvidia-smi -L | wc -l')
    if r != '1' and r != '2':
        nvidia_info = sudo("lspci | grep -i nvidia")
        if nvidia_info:
            nvidia_install()
    sudo('apt -y autoremove')
    sudo('apt -y purge')


@parallel
def nvidia_remove():
    sudo('apt-get --purge remove -y nvidia-*')
    sudo('apt-get --purge remove -y libnvidia-*')
    sudo('apt-get remove --purge nvidia-\*')
    sudo('apt-get purge nvidia*')
    sudo('apt autoremove --purge -y')

    sudo('apt -y autoremove')
    sudo('apt -y purge')
    sudo('rmmod nvidia-drm')
    sudo('rmmod nvidia-modeset')
    sudo('rmmod nvidia_uvm')
    sudo('rmmod nvidia')
    sudo('rm -rf /lib/modules/`uname -r`/kernel/nvidia-460')
    sudo('rm -rf /lib/modules/`uname -r`/updates/dkms/nvidia*')


@parallel
def nvidia_cp_drive(nvidia_info=None):
    drive_name = 'NVIDIA-Linux-x86_64-'
    if not nvidia_info:
        nvidia_info = sudo("lspci | grep -i nvidia").split('\n')[0]
    if "30" in nvidia_info or '220' in nvidia_info:
        drive_name += '460.39.run'
    else:
        drive_name += '450.102.04.run'
    put('/home/ps/share/hdd/nvidia/%s' % drive_name, '/home/ps')
    return drive_name


@parallel
def nvidia_install():
    nvidia_info = sudo("lspci | grep -i nvidia").split('\n')[0]
    with settings(warn_only=True):
        nvidia_remove()
        drive_name = nvidia_cp_drive(nvidia_info)
        sudo("chmod a+x %s" % drive_name)
    sudo("sudo ./%s --ui=none --no-questions" % drive_name)


# @parallel
def ast():
    put("/home/ps/share/hdd/data/ast_dp501_fw.bin", "/home/ps")
    sudo("mv /home/ps/ast_dp501_fw.bin /lib/firmware/")


@parallel
def ram():
    run('echo 53687091200 | sudo tee /proc/sys/vm/dirty_bytes')
    run('echo 10737418240 | sudo tee /proc/sys/vm/dirty_background_bytes')
    run('echo 1000 | sudo tee /proc/sys/vm/vfs_cache_pressure')
    run('echo 100 | sudo tee /proc/sys/vm/dirty_writeback_centisecs')
    run('echo 100 | sudo tee /proc/sys/vm/dirty_expire_centisecs')


def check_md():
    info_list = sudo('fdisk -l | grep "T"').split('\n')
    for info in info_list:
        if info:
            print(info)


def check_ssd_type():
    info = sudo('fdisk -l | grep "T"')
    if '3.7 TiB' in info:
        print('yes')


@parallel
def wipefs():
    disks = sudo('lsblk | grep T').split('\n')
    for disk in disks[1:]:
        disk = disk.split(' ')[0]
        sudo("sudo wipefs -af /dev/%s" % disk)
    with settings(warn_only=True):
        reboot(600)


@parallel
def umount():
    with settings(warn_only=True):
        sudo('umount /dev/md0')
    info = sudo('mdadm -D /dev/md0 | grep /dev/').split('\n')
    with settings(warn_only=True):
        sudo('mdadm -S /dev/md0')
    dev1 = info[1].split(' ')[-1]
    dev2 = info[2].split(' ')[-1]

    sudo('mdadm --misc --zero-superblock %s' % dev1)
    sudo('mdadm --misc --zero-superblock %s' % dev2)
    sudo('rm -f /etc/mdadm.conf')
    sudo('sed -i "/mnt\/md/d" /etc/fstab')
    wipefs()


@parallel
def umount_127():
    with settings(warn_only=True):
        sudo('umount /dev/md127')
    info = sudo('mdadm -D /dev/md127 | grep /dev/').split('\n')
    with settings(warn_only=True):
        sudo('mdadm -S /dev/md127')
    dev1 = info[1].split(' ')[-1]
    dev2 = info[2].split(' ')[-1]

    sudo('mdadm --misc --zero-superblock %s' % dev1)
    sudo('mdadm --misc --zero-superblock %s' % dev2)
    sudo('rm -f /etc/mdadm.conf')
    sudo('sed -i "/mnt\/md/d" /etc/fstab')
    wipefs()


@parallel(5)
def md_ssd():
    sudo('mkdir -p /mnt/ssd1')
    sudo('mkdir -p /mnt/ssd2')
    sudo("chown ps.ps /mnt/ssd1")
    sudo("chown ps.ps /mnt/ssd2")


@parallel
def md():
    if run('df -H | grep /mnt/md0 | wc -l') == '1':
        return
    infos = run('lsblk | grep T').split('\n')
    infos = infos[1:]
    cmds = 'mdadm --create -f --verbose /dev/md0 --level=0 --raid-devices=%s' % len(infos)
    for info in infos:
        ssd = '/dev/' + info.split(' ')[0]
        if 'nvme' not in ssd:
            raise Exception('wrong ssds')
        cmds += ' %s' % ssd
    with settings(prompts={'Continue creating array? ': 'y'}):
        sudo(cmds)
    sudo("mdadm -D --scan > /etc/mdadm.conf")

    sudo("mkfs.xfs -f /dev/md0")
    sudo("mkdir -p /mnt/md0")
    sudo("mount -t xfs -o noatime /dev/md0 /mnt/md0")
    sudo("chown ps.ps /mnt/md0")

    uuid = get_uuid("/dev/md0")
    sudo('sed -i "/mnt\/md0/d" /etc/fstab')
    sudo('echo "/dev/disk/by-uuid/%s /mnt/md0 xfs noatime 0 0" >> /etc/fstab' % uuid)


def md_special():
    sudo("mkfs.xfs -f /dev/mapper/VolGroup00-lv01")
    sudo("mkdir -p /mnt/md0")
    sudo("mount -t xfs -o noatime /dev/mapper/VolGroup00-lv01 /mnt/md0")
    sudo("chown ps.ps /mnt/md0")

    uuid = get_uuid("/dev/mapper/VolGroup00-lv01")
    sudo('sed -i "/mnt\/md0/d" /etc/fstab')
    sudo('echo "/dev/disk/by-uuid/%s /mnt/md0 xfs noatime 0 0" >> /etc/fstab' % uuid)


@parallel
def md_80T():
    hdd = run('lsblk | grep T | grep sd')
    if '/mnt/md0' in hdd:
        return
    with settings(warn_only=True):
        sudo('rm -r m.deb*')
        sudo('curl 183.36.3.160:50085/reraid5.sh | bash')
    hdd = run('lsblk | grep T | grep sd')
    if '/mnt/md0' in hdd:
        return
    hdd = hdd.split(' ')[0]
    device = '/dev/' + hdd
    sudo('mkfs.xfs -f %s' % device)
    sudo('mkdir -p  /mnt/md0')
    sudo('mount %s  /mnt/md0' % device)
    with settings(warn_only=True):
        sudo('rm -r m.deb*')


@parallel
def ssd():
    sys_ssd = get_sys_ssd()
    ssd2t = sudo('fdisk -l | grep "1.8 TiB" | grep -v %s' % sys_ssd).split(' ')[1].strip(':')
    if not check_ssd(ssd2t):
        mount_ssd(ssd2t, '/mnt/ssd1')

    ssd4t = sudo('fdisk -l | grep "3.7 TiB"').split(' ')[1].strip(':')
    if not check_ssd(ssd4t):
        mount_ssd(ssd4t, '/mnt/ssd2')


def check_ssd(dev):
    r = run('df | grep %s | wc -l' % dev)
    return r == '1'


def mount_80T():
    dev = sudo('fdisk -l | grep T').split(' ')[1].strip(':')
    path = '/mnt/md0/'
    sudo('mkfs.xfs -f %s' % dev)
    sudo('mkdir -p %s' % path)
    sudo('mount -t xfs -o noatime %s %s' % (dev, path))
    sudo('chown ps.ps %s' % path)

    uuid = get_uuid(dev)
    sudo('sed -i "/%s/d" /etc/fstab' % uuid)
    sudo('echo "/dev/disk/by-uuid/%s %s xfs noatime 0 0" >> /etc/fstab' % (uuid, path))


def mount_ssd(dev, path):
    if len(dev) != 12:
        raise Exception('cannot detect ssd %s' % dev)

    sudo('mkfs.xfs -f %s' % dev)
    sudo('mkdir -p %s' % path)
    sudo('mount -t xfs -o noatime %s %s' % (dev, path))
    sudo('chown ps.ps %s' % path)

    uuid = get_uuid(dev)
    sudo('sed -i "/%s/d" /etc/fstab' % uuid)
    sudo('echo "/dev/disk/by-uuid/%s %s xfs noatime 0 0" >> /etc/fstab' % (uuid, path))


def get_uuid(dev):
    r = sudo('blkid | grep %s' % dev)
    path, uuid, t = r.strip().split(' ')
    uuid = uuid[6:-1]

    print(uuid)
    if len(uuid) != 36:
        raise Exception('parse uuid error %s' % uuid)

    return uuid


def get_sys_ssd():
    sys_ssd = None
    df = sudo('df')
    for line in df.split('\n'):
        line = line.strip().split(' ')
        if line[-1] != '/':
            continue

        sys_ssd = line[0][:12]

    if sys_ssd is None:
        raise Exception('cannot detect system ssd')

    return sys_ssd


@parallel
def swap():
    swap_path = '/mnt/ssd1/swapfile'

    ret, swapfile = check_swap()
    if ret and swapfile == swap_path:
        logging.info('swap has been set')
        return

    if swapfile is not None:
        sudo('swapoff -v %s' % swapfile)
        sudo('rm %s' % swapfile)
    sudo('dd if=/dev/zero of=%s bs=1024 count=67108864' % swap_path)
    sudo('chmod 600 %s' % swap_path)
    sudo('mkswap %s' % swap_path)
    sudo('swapon %s' % swap_path)

    sudo('sed -i "/swap/d" /etc/fstab')
    sudo('echo "%s none swap sw 0 0" >> /etc/fstab' % swap_path)

    swappiness()

    ret, swapfile = check_swap()
    if not ret:
        raise Exception('set swap failed: %s' % swapfile)
    logging.info('final swap %s' % swapfile)


def swappiness():
    sudo('sysctl vm.swappiness=2')
    sudo('sed -i "/swappiness/d" /etc/sysctl.conf')
    sudo('echo "vm.swappiness=2" >> /etc/sysctl.conf')


def check_swap():
    try:
        swapfile = sudo('swapon --show')
        swapfile = swapfile.split('\n')
        swapfile = swapfile[1].split(' ')
        swapfile, swapsize = swapfile[0], swapfile[3]
    except:
        return False, None

    return swapsize == '64G', swapfile


@parallel
def check_gpu():
    r = run('nvidia-smi -L | wc -l')
    if r == '3' or r == '4':
        sudo('supervisorctl stop worker')
        with settings(warn_only=True):
            reboot(600)


@parallel
def nfs():
    ip = local('hostname -I', capture=True)
    run('mkdir -p /home/ps/share')
    with settings(warn_only=True):
        sudo('umount /home/ps/share')
        sudo('mount -t nfs -o hard,intr,bg,nofail,noatime %s:/home/ps/share /home/ps/share' % ip)
    sudo('chown ps.ps /home/ps/share')


@parallel(1)
def check_nfs():
    run('df -H | grep share')


@parallel
def chown():
    sudo('chown ps.ps /mnt/ssd2/')


@parallel
def param():
    sudo("chown ps.ps /mnt/md0")
    run('rm -rf /mnt/md0/filecoin-proof-parameters')
    run('cp -r /home/ps/share/ssd/data/filecoin-proof-parameters /mnt/md0/')


@parallel
def param_vk():
    run('cp /home/ps/share/ssd/data/filecoin-proof-parameters/*.vk /mnt/md0/filecoin-proof-parameters/')


@parallel
def param_ssd2():
    # sudo("chown ps.ps /mnt/md0")
    run('rm -rf /mnt/ssd2/filecoin-proof-parameters')
    run('cp -r /home/ps/share/ssd/data/filecoin-proof-parameters /mnt/ssd2/')


@parallel
def param_data():
    # sudo("chown ps.ps /mnt/md0")
    run('rm -rf /data/filecoin-proof-parameters')
    run('cp -r /home/ps/share/ssd/data/filecoin-proof-parameters /data/')


@parallel
def param_check():
    run('md5sum /mnt/md0/filecoin-proof-parameters/* > /mnt/md0/filecoin-proof-parameters.md5')
    m = run('md5sum /mnt/md0/filecoin-proof-parameters.md5')


@parallel
def param_3_check():
    run('md5sum /mnt/ssd2/filecoin-proof-parameters/* > /mnt/ssd2/filecoin-proof-parameters.md5')
    m = run('md5sum /mnt/ssd2/filecoin-proof-parameters.md5')


@parallel
def bench():
    run('nohup /home/ps/share/ssd/script/run_bench.sh > /dev/null 2>&1 &', pty=False)


@parallel
def worker_stop():
    sudo('supervisorctl stop worker')


@parallel
def worker_start():
    sudo('supervisorctl start worker')


@parallel
def worker_remove():
    with settings(warn_only=True):
        worker_stop()

    sudo('rm -rf /home/ps/data/lotus* /home/ps/data/run* /mnt/ssd*/lotus* /mnt/md*/lotus* /etc/supervisor/conf.d/*')


@parallel
def worker_init():
    nfs()
    run('mkdir -p /home/ps/data/')
    run('cp /home/ps/share/ssd/script/run_worker.sh /home/ps/data/')
    sudo('cp /home/ps/share/ssd/conf/worker.conf /etc/supervisor/conf.d/')
    # sudo('supervisorctl reload')
    with settings(warn_only=True):
        reboot(600)


@parallel
def worker_mount_hdd():
    run('/home/ps/share/ssd/script/mount_hdd.sh')


@parallel
def worker_status():
    sudo('supervisorctl status')


@parallel(1)
def check_gpu_status():
    run('nvidia-smi -L')


@parallel(1)
def lsblk():
    r = run('lsblk | grep T')


def md_3_fix():
    data = run('lsblk -J')
    data = json.loads(data)
    disk_info_list = []
    for disk_info in data.get('blockdevices'):
        if not disk_info.get('mountpoint') and not disk_info.get('children'):
            disk_info_list.append(disk_info)
        elif disk_info.get('children'):
            flag = False
            for children in disk_info.get('children'):
                if children.get('mountpoint'):
                    flag = True
                    break
            if not flag:
                disk_info_list.append(disk_info)

    ssd1 = disk_info_list[0].get('name')
    ssd2 = disk_info_list[1].get('name')

    with settings(prompts={'Continue creating array? ': 'y'}):
        sudo("mdadm --create -f --verbose /dev/md0 --level=0 --raid-devices=2 /dev/%s /dev/%s" % (ssd1, ssd2))
    sudo("mdadm -D --scan > /etc/mdadm.conf")

    sudo("mkfs.xfs -f /dev/md0")
    sudo("mkdir -p /mnt/")
    sudo("mount -t xfs -o noatime /dev/md0 /mnt/")
    sudo("chown ps.ps /mnt/")

    uuid = get_uuid("/dev/md0")
    sudo('sed -i "/mnt\/d" /etc/fstab')
    sudo('echo "/dev/disk/by-uuid/%s /mnt/ xfs noatime 0 0" >> /etc/fstab' % uuid)


@parallel
def swap_128():
    swap_path = '/mnt/md0/swapfile'

    ret, swapfile = check_swap_128()
    if ret and swapfile == swap_path:
        logging.info('swap has been set')
        return

    if swapfile is not None:
        sudo('swapoff -v %s' % swapfile)
        sudo('rm %s' % swapfile)
    sudo('dd if=/dev/zero of=%s bs=1048576 count=131072' % swap_path)
    sudo('chmod 600 %s' % swap_path)
    sudo('mkswap %s' % swap_path)
    sudo('swapon %s' % swap_path)

    sudo('sed -i "/swap/d" /etc/fstab')
    sudo('echo "%s none swap sw 0 0" >> /etc/fstab' % swap_path)

    swappiness()

    ret, swapfile = check_swap_128()
    if not ret:
        raise Exception('set swap failed: %s' % swapfile)
    logging.info('final swap %s' % swapfile)


def check_swap_128():
    try:
        swapfile = sudo('swapon --show')
        swapfile = swapfile.split('\n')
        swapfile = swapfile[1].split(' ')
        swapfile, swapsize = swapfile[0], swapfile[2]
    except:
        return False, None

    return swapsize == '128G', swapfile


@parallel
def swap_64():
    swap_path = '/swapfile'

    ret, swapfile = check_swap_64()
    if ret and swapfile == swap_path:
        logging.info('swap has been set')
        return

    if swapfile is not None:
        sudo('swapoff -v %s' % swapfile)
        sudo('rm %s' % swapfile)
    sudo('dd if=/dev/zero of=%s bs=1048576 count=65536' % swap_path)
    sudo('chmod 600 %s' % swap_path)
    sudo('mkswap %s' % swap_path)
    sudo('swapon %s' % swap_path)

    sudo('sed -i "/swap/d" /etc/fstab')
    sudo('echo "%s none swap sw 0 0" >> /etc/fstab' % swap_path)

    swappiness()

    ret, swapfile = check_swap_64()
    if not ret:
        raise Exception('set swap failed: %s' % swapfile)
    logging.info('final swap %s' % swapfile)


def check_swap_64():
    try:
        swapfile = sudo('swapon --show')
        swapfile = swapfile.split('\n')
        swapfile = swapfile[1].split(' ')
        swapfile, swapsize = swapfile[0], swapfile[3]
    except:
        return False, None

    return swapsize == '64G', swapfile


@parallel
def install_nvme():
    sudo("apt install -y nvme-cli")


@parallel
def stop_recover():
    with settings(warn_only=True):
        run("ps -ef | grep lotus-recover | grep -v grep | awk '{print $2}' | xargs kill -9")
    run('rm -rf /mnt/md0/lotusrecover /mnt/md0/lotusrecover.tmp')


def recover_sector():
    stop_recover()
    run('$(nohup /home/ps/share/ssd/script/run_recover.sh > /home/ps/recover.log 2>&1 &) && sleep 10')


@parallel(100)
def move_recover():
    finished = run('ps -ef | grep lotus-recover | grep -v grep | wc -l')
    if finished != '0':
        return

    target_list = []
    target = random.choice(target_list)

    run(
        'for F in `ls /mnt/md0/lotusrecover/sealed/`; do cp -r /mnt/md0/lotusrecover/sealed/$F %s/sealed/$F.tmp; done' % target)
    run(
        'for F in `ls /mnt/md0/lotusrecover/cache/`; do cp -r /mnt/md0/lotusrecover/cache/$F %s/cache/$F.tmp; done' % target)
    run('for F in `ls /mnt/md0/lotusrecover/sealed/`; do mv %s/sealed/$F.tmp %s/sealed/$F; done' % (target, target))
    run('for F in `ls /mnt/md0/lotusrecover/cache/`; do mv %s/cache/$F.tmp %s/cache/$F; done' % (target, target))


@parallel
def remove_raid0():
    sudo("umount /dev/md0")
    sudo("mdadm -S /dev/md0")


@parallel
def remove_swap_128():
    sudo("swapoff -v /mnt/md0/swapfile")
    sudo('sed -i "/swap/d" /etc/fstab')
    sudo("rm /mnt/md0/swapfile")


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


@parallel
def firm():
    put("/home/ps/share/hdd/data/intelmas_1.1.884-0_amd64.deb", "/home/ps")
    sudo('dpkg -i /home/ps/intelmas_1.1.884-0_amd64.deb')

    with settings(warn_only=True):
        for i in range(7):
            sudo('intelmas load -f -intelssd %s' % i)

    run('rm -f /home/ps/intelmas_1.1.884-0_amd64.deb')


@parallel
def remove_gpu_status():
    sudo('apt-get --purge remove -y nvidia-*')
    sudo('apt-get --purge remove -y libnvidia-*')
    sudo('apt-get remove --purge nvidia-\*')
    sudo('apt-get purge nvidia*')
    sudo('apt autoremove --purge -y')
    sudo('rmmod nvidia_drm')
    sudo('rmmod nvidia_modeset')
    sudo('rmmod nvidia_uvm')
    sudo('rmmod nvidia')
    sudo('rm -rf /lib/modules/`uname -r`/kernel/nvidia-460')
    sudo('rm -rf /lib/modules/`uname -r`/updates/dkms/nvidia*')
    sudo('apt -y install nvidia-driver-460-server')


@parallel
def worker_belong_to():
    host_ip = local('hostname -I')
    nfs_info = run('df -H | grep share')
    if host_ip not in nfs_info:
        print(nfs_info)


@parallel(1)
def nvme_status():
    disks = sudo('lsblk | grep T | grep disk | grep 1.8').split('\n')
    if disks:
        for disk in disks:
            disk = disk.split(' ')[0]
            sudo('nvme smart-log /dev/%s' % disk)
            # sudo('nvme intel smart-log-add /dev/%s' % disk)


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
def clear_md0():
    hdd = run('lsblk | grep T | grep sd')
    hdd = hdd.split(' ')[0]
    device = '/dev/' + hdd
    with settings(warn_only=True):
        sudo('umount /mnt/md0')
        sudo('swapoff -v /mnt/md0/swapfile')
        sudo('rm -rf /mnt/md0')
        sudo('mkdir -p /mnt/md0')
        sudo('mount %s  /mnt/md0' % device)
        sudo("chown ps.ps /mnt/md0")


@parallel
def check_host():
    with settings(warn_only=True):
        nfs_info = sudo('df -H | grep share')
        minerip = local('hostname -I', capture=True)
        workerip = run('hostname -I')
        online_workers = local('lotus-miner sealing workers |grep host', capture=True)
    print(workerip, minerip in nfs_info, workerip in online_workers)
    f = open("workers.lst", "a+")
    if minerip in nfs_info:
        f.write(str('%s\n' % workerip))
    f.close()


@parallel(1)
def iperf_to_storage():
    storages = []
    storages.extend(get_part(part_name='storage'))
    for ip in storages:
        run('iperf -t 1 -c %s' % ip)


@parallel
def one_key():
    install()
    add_ssh_key()
    time_adjust()
    firm()
    restart()
    md()
    nfs()
    swap_128()
    param()
    worker_remove()
    # worker_init()
