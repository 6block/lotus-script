import logging

from fabric.api import hide, env, run, sudo, reboot, settings, parallel, local, put

logging.basicConfig(level=logging.ERROR)

env.user = 'ps'
env.password = raw_input('Enter Password:')


def get_part(part_name='storage', size=1000, direction=True):
    hosts = []
    with open('../%s' % part_name) as f:
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
    hosts.extend(get_part(part_name='storage.lst'))
    hosts.extend(get_part(part_name='computing.lst'))
    # hosts = hosts[:1]
    logging.info("%s %s" % (hosts, len(hosts)))
    return hosts


env.hosts = get_hosts()


@parallel
def hello():
    with hide('aborts', 'status', 'warnings', 'running', 'stdout', 'stderr'):
        run('hostname -I')


@parallel
def get_cpu_info():
    with hide('aborts', 'status', 'warnings', 'running', 'stdout', 'stderr'):
        info = run('cat /proc/cpuinfo')
        if '7F52' in info:
            print('Error   7f52')


@parallel
def restart():
    with settings(warn_only=True):
        reboot(600)


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
def install():
    sudo("apt update")
    sudo('apt -y upgrade')
    sudo("apt install -y ubuntu-drivers-common ntpdate iperf tree  nfs-common")
    sudo("update-pciids")
    r = run('nvidia-smi -L | wc -l')
    if r != '1' and r != '2':
        nvidia_info = sudo("lspci | grep -i nvidia")
        if nvidia_info:
            sudo('apt-get --purge remove -y nvidia-*')
            sudo('apt-get --purge remove -y libnvidia-*')
            nvidia_info = nvidia_info.split('\n')[0]
            if "30" in nvidia_info or '2206' in nvidia_info:
                print('3080~3090')  # install 3080Ti or 3090Ti steps in workers
            else:
                sudo('apt -y install nvidia-driver-440-server')  # install 2080Ti
    sudo('apt -y autoremove')
    sudo('apt -y purge')


@parallel
def firm():
    put("/home/ps/share/hdd/data/intelmas_1.1.884-0_amd64.deb", "/home/ps")
    sudo('dpkg -i /home/ps/intelmas_1.1.884-0_amd64.deb')

    with settings(warn_only=True):
        for i in range(7):
            sudo('intelmas load -f -intelssd %s' % i)

    run('rm -f /home/ps/intelmas_1.1.884-0_amd64.deb')


def firm_show():
    sudo('intelmas show -intelssd')


@parallel(3)
def iperf():
    ip = local('hostname -I', capture=True)
    run('iperf -t 1 -c %s' % ip)


@parallel
def rm_auto_upgrade():
    with settings(warn_only=True):
        sudo('rm /etc/apt/apt.conf.d/20auto-upgrades')


@parallel
def one_key():
    install()
    add_ssh_key()
    time_adjust()
    firm()
    rm_auto_upgrade()
    restart()
