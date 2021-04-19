# 6block集群安装步骤

# 欢迎加入6block

```
服务器运维 
岗位职责
1. 服务器的操作系统、硬件驱动、软件的部署和配置
2. 服务器故障的监控、分析和定位
3. 对于硬件故障，配合机房运维人员进行硬件的更换，完成更换后的驱动安装、软件配置等工作
4. 对于软件故障，配合软件研发人员进行日志收集、分析和解决
职位要求
1. 能够看懂当前仓库的所有文档和脚本
2. 强大的学习能力，能够快速掌握服务器的常见故障
3. 有Python、Shell等编程能力者优先

简历投递邮箱：salsa@6block.com
```

# 准备

## 安装操作系统
```
1. 所有机器安装 Ubuntu 18.04
   http://cdimage.ubuntu.com/ubuntu/releases/18.04/release/ubuntu-18.04.5-server-amd64.iso
2. 安装时，用户名设置为 ps，Hostname 设置为各不相同的
```

## 在主机上下载

```
1. 创建目录/home/ps/share/hdd/data/
2. 下载相关软件
    wget -P ~/share/hdd/data/ https://6block.s3.cn-north-1.jdcloud-oss.com/software/Intel%C2%AE_MAS_CLI_Tool_1.1_Linux.zip 
    wget -P ~/share/hdd/data/ https://6block.s3.cn-north-1.jdcloud-oss.com/software/ast_dp501_fw.bin.gz
    wget -P ~/share/hdd/data/ https://6block.s3.cn-north-1.jdcloud-oss.com/software/zap-pretty
3. 解压相关软件
    cd ~/share/hdd/data/ && unzip Intel%C2%AE_MAS_CLI_Tool_1.1_Linux.zip 
    cd ~/share/hdd/data/ &&  gzip -dk ast_dp501_fw.bin.gz
4. 下载显卡驱动
    wget -P ~/share/hdd/nvidia/ https://6block.s3.cn-north-1.jdcloud-oss.com/software/NVIDIA-Linux-x86_64-450.102.04.run
    wget -P ~/share/hdd/nvidia/ https://6block.s3.cn-north-1.jdcloud-oss.com/software/NVIDIA-Linux-x86_64-460.39.run
```

# 配置

## 主机

```
# 首先获取脚本（fabric_host）
git clone https://github.com/6block/lotus-script.git
cd lotus-script/fabric_host

# 安装fabric
sudo apt install fabric

# 格式化并挂载一张8TB的ssd
fab mount

# 生成密钥
ssh-keygen -C 名称

# 创建所需目录
mkdir -p ~/share/ssd/script/fabric
mkdir -p ~/share/ssd/data
mkdir -p ~/share/hdd/data
mkdir -p ~/share/hdd/log
mkdir -p ~/share/ssd/data/filecoin-proof-parameters

# 创建所需文件
touch ~/share/ssd/script/fabric/computing.lst (填写计算workerIP)
touch ~/share/ssd/script/fabric/storage.lst (填写存储机IP)

# 获取脚本fabric_storage、fabric_worker、fabric_all,放到对应位置
#dest ~/share/ssd/script/fabric/fabric_worker
#dest ~/share/ssd/script/fabric/fabric_storage
#dest ~/share/ssd/script/fabric/fabric_all

# 查看apt源，如果不是aliyun，请替换为aliyun
fab apt_source

# 安装一堆东西 
fab install

# 删除自动更新的配置
fab rm_auto_upgrade

# 时钟校准
fab time_adjust

# 关超线程。lotus同步相关的代码里有个bug，需要通过关闭超线程来绕开，使用以下脚本
fab thread
fab ast

# SSD固件升级
fab firm
fab firm_show

# zap-pretty，一个看日志的工具
fab zap

# 将share目录用nfs共享，这里网段要根据实际情况修改
fab nfs

# 环境变量,根据集群类型选择
fab filestar_source
fab filecoin_source

# 重启后看看环境变量是否成功,看看share目录是否自动挂载
fab restart
fab check_env

# 从别打机器拷贝或下载filecoin-proof-parameters，这是zk参数，上百GB
#dest ~/share/ssd/data/filecoin-proof-parameters

# 检查刚才那zk参数文件的md5完整性
lotus fetch-params 32GiB
```

## 全部
```
cd ~/share/ssd/script/fabric/fabric_all

# 查看apt源，如果不是aliyun，请替换为aliyun
fab apt_source

# 安装一堆东西 
fab install

# 删除自动更新的配置
fab rm_auto_upgrade

# 时钟校准
fab time_adjust

# 把pubkey添加到子机器上
fab add_ssh_key

# SSD固件
fab firm
```

## 存储

```
cd ~/share/ssd/script/fabric/fabric_storage

# 主机nfs配置优化
sudo su
echo "options sunrpc tcp_slot_table_entries=1024" >> /etc/modprobe.d/sunrpc.conf
echo "options sunrpc tcp_max_slot_table_entries=1024" >>  /etc/modprobe.d/sunrpc.conf
sysctl -w sunrpc.tcp_slot_table_entries=1024
cat /proc/sys/sunrpc/tcp_slot_table_entries

sudo vi /etc/sysctl.conf
# 末尾插入
net.core.rmem_default = 1342177
net.core.rmem_max = 16777216
net.core.rmem_max = 16777216
net.core.wmem_default = 1342177
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 1342177 16777216
net.ipv4.tcp_wmem = 4096 1342177 16777216
net.core.netdev_max_backlog = 300000
net.ipv4.tcp_fin_timeout = 10
# 生效
sudo sysctl -p

# 安装一堆东西
fab install

# 生成密钥并设置与主机之间的免密
fab add_ssh_key

# 时钟校准
fab time_adjust

# SSD固件升级
fab firm
fab restart

# 测试与主机之间的网络
fab iperf

# 格式化磁盘
fab mkfs
fab mount
fab mount_res
fab restart

# NFS服务端配置。如果是外部集群，要改网段
fab export
fab improve

# 在主机挂载NFS
fab client

# 查看下是NFS是否都正常挂载在主机上，应当是每个存储机器挂载过来36个盘
df -H | grep disk36
```

## 计算

### 3系

```
cd ~/share/ssd/script/fabric/fabric_worker

#  如果是从别的集群拉过来的worker，则先停worker
fab worker_remove

# 安装一堆东西
fab install

# 上3系worker看一下，如果 / 路径已经挂载了一张8TB的raid盘，就不用下面这步了
fab ssd

# 配置3系的swap 慎重此步骤中 要分清楚 是两张8T SSD还是1张2T，1张4T和1张8T
fab swap

# 挂载主机的share目录
fab nfs

# 下载参数
fab param

# 让显卡驱动生效
fab restart
```

### 7系

```
cd ~/share/ssd/script/fabric/fabric_worker

# 安装一堆东西
fab install

# 挂载主机的share目录
fab nfs

#1. 脚本放到 fabric_worker 下的 fabfile.py 里，有的集群是 2080Ti 和 3080 混合的，只对装的是 3080 的worker做操作
#2. 先在主机把驱动拉到对应目录，脚本里写的是 ~/share/ssd/NVIDIA-Linux-x86_64-460.39.run
#3. 如果worker正在运行先停worker，然后 nvidia_cp，nvidia_remove_3080() ，怕有问题可以先试一台，有报错可以看下为啥，然后 nvidia_install_3080，成功后 fab restart

关闭超线程部分最后一步如果有warn且内容和缺少下面这个文件相关，则要拷贝这个文件过来，文件从其他机器的~/share/hdd/data/下拷贝过去
# fab ast

# 检查多张ssd是否做成raid并挂载到/mnt/md0下
fab lsblk

# 把多张ssd做成raid，这步会遇到各种问题
# 比如ssd大小不对，就要注释掉这个ip回头让现场处理
# 比如磁盘有分区，则要手动删除分区，重启生效，然后继续。步骤是：fdisk 盘，m g w。
# 有可能要删掉raid, fab umount

# 多张ssd是否做成raid并挂载到/mnt/md0
fab md

# 创建swap
fab swap_128

# 下载参数
fab param

# 让显卡驱动生效
fab restart
# 检查显卡驱动是否安装成功
fab check_gpu_status
```

## 部署挖矿

### 前期准备工作

```
# 挖矿程序
mkdir ~/share/ssd/bin
cd ~/share/ssd/bin

# 把需要的包拷过来
tar zvxf ./lotus-miner.xxx.tar.gz
rm -rf ./lotus-miner.xxx.tar.gz
mkdir bin_star
mv ./lotus* ./bin_star/
sudo cp ./bin_star/* /usr/local/bin

# 获取脚本deploy.py放到对应位置
#dest ~/share/ssd/script

# 下载snapshot到本地
```

### 详细版部署流程

```
# lotus
cd ~/share/ssd/script

python3 ./deploy.py gen-run-lotus

sudo python3 ./deploy.py lotus-superv-conf

# 对于后期部署的节点，可以导入快照加速同步，具体流程参见目录
vi run_lotus_v0.sh
#~/share/ssd/bin/bin_$V/lotus daemon &
~/share/ssd/bin/bin_$V/lotus daemon --import-snapshot /快照存放路径 &

sudo supervisorctl update lotus_v0
tail -f ~/share/hdd/log/lotus_v0.log 查看日志是否正常启动

# 修改lotus的配置
python3 ./deploy.py update-lotus-config

# 快照倒入完成后，取消导入快照同步
vi run_lotus_v0.sh
~/share/ssd/bin/bin_$V/lotus daemon &
#~/share/ssd/bin/bin_$V/lotus daemon --import-snapshot /快照存放路径 &

# 重启让配置生效 
sudo supervisorctl restart lotus_v0

# 拷贝api和token到~/share/ssd/data/lotus
mkdir ~/share/ssd/data/lotus
cp ~/share/ssd/data/lotus_v0/api ~/share/ssd/data/lotus
cp ~/share/ssd/data/lotus_v0/token ~/share/ssd/data/lotus

lotus net listen 看下peerid是否正常
lotus sync wait 等待同步完成

新建地址 lotus wallet new bls
或者导入已有私钥 echo "xxx" | lotus wallet import
lotus wallet set-default 地址

# 给钱包地址打0.2个币
```

```
# 注册miner
lotus wallet balance 确保余额足够

python3 ./deploy.py gen-init-miner // 新建miner直接回车，恢复旧miner需输入
./init_miner_v0.sh           // init_miner的时候卡住是正常的，是消息在等待确认，不要中断重复执行，避免多次init而创建多个矿工

# dealfilter.pl
python3 ./deploy.py gen-default-filter

# 修改miner的配置文件
python3 ./deploy.py update-miner-config

# 生成mount_hdd.sh
检查一下 ./fabric/fabric_storage/fabfile.py 的shell()函数
python3 ./deploy.py gen-mount-hdd
# 生成 run_miner.sh 
python3 ./deploy.py gen-run-miner

# 添加 miner_v0 到 supervisor
sudo python3 ./deploy.py miner-superv-conf
sudo supervisorctl update miner_v0

# 拷贝api和token到~/share/ssd/data/lotusminer
python3 ./deploy.py update-miner-api

# 若miner没起来，可以 tail -f ~/share/hdd/log/miner_v0.log 看日志

lotus-miner --color info

# 设置接单相关参数
lotus-miner storage-deals set-ask --price 1 --verified-price 1 --min-piece-size 256B --max-piece-size 32GiB

# 把网盘添加到miner上
cd ./fabric/fabric_storage
vim fabfile.py 检查attach函数中定义的storage是否正确，并确保get_hosts()获取的是全部机器
fab attach

cd ~/share/ssd/script
python3 ./deploy.py check-attach 检查是否正确, 留意磁盘数是否符合预期
```

```
# 启动worker
# 记得先check一下主机(~/share/ssd/data/filecoin-proof-parameters)和一个worker上(/mnt/md0/filecoin-proof-parameters)的zk参数是否完整，不完整的话需要将参数拉好然后删除worker上的旧参数然后重新分发(fab param)

# 生成 worker.sh run_worker.sh
python3 ./deploy.py gen-run-worker

# 生成 /home/ps/share/ssd/conf/worker.conf
python3 ./deploy.py gen-worker-conf

cd ~/share/ssd/script/fabric/fabric_worker
fab worker_remove
fab worker_init

# 验证有没有成功跑起
python3 ./deploy.py check-worker 看是否都连上了，通常worker重启后10分钟内都应该连上
没连上可以 tail -f ~/share/hdd/log/worker_xxx.log 看一下日志,或者登上worker看一下~/worker.log
```

```
# 为 windowPOST 设置专门的账号 
lotus-miner actor control list --verbose 看一下是否已经设置过
lotus wallet new bls 创建一个新账号
lotus send --from <address> t3defg... 0.1 向这个账号打一些币
lotus-miner actor control set --really-do-it t3defg... 设置地址
lotus state wait-msg bafy2.. 等待消息确认
lotus-miner actor control list --verbose 查看是否添加成功
```

# filecoin部署相关脚本及软件使用

## 运行filecoin需要到相关脚本

```
1.  安装主机环境fibric_host
    下载到home目录
2.  安装计算机器及存储机器环境fabric
    下载到~/share/ssd/script/目录
    其中fabric目录下的computing.lst、storage.lst列表中ip依照实际操控IP填写
3.  部署挖矿脚本deploy.py
    下载到~/share/ssd/script/
```
