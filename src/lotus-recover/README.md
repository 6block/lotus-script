# lotus-recover使用教程

## 恢复流程

```
1.  下载lotus-recover程序
2.  使用前配置如下环境变量
    export FIL_PROOFS_MAXIMIZE_CACHING=1
    export FIL_PROOFS_USE_GPU_COLUMN_BUILDER=1
    export FIL_PROOFS_USE_GPU_TREE_BUILDER=1
    export FIL_PROOFS_USE_MULTICORE_SDR=1
    export FIL_PROOFS_MULTICORE_SDR_PRODUCERS=1
    export FIL_PROOFS_SDR_PARENTS_CACHE_SIZE=1073741824
    export FIL_PROOFS_PARENT_CACHE=/mnt/md1/parent_cache
3.  执行：./lotus-recover recover --miner-addr=t01000 --work-dir=/mnt/md0 --sector-size=64GiB --parallel=2  --sector-id=1 --sector-id=2 --ticket=xxx --ticket=xxx --seal-proof-type=9 --seal-proof-type=9 --commR=xxx --commR=xxx --storage-dir=/mnt/$storage_ip/disk28/$hostname.tmp>> ~/share/hdd/log/recover-$hostname.log 2>&1 &
4.  进程结束后，重启miner
```


## 参数解释

```
--work-dir 工作路径，存放恢复过程中的临时文件，一般设置为worker的ssd上的目录
--storage-dir 存储目录，可设置多个，由程序随机选择
--sector-size 扇区大小
--miner-addr 矿工号
--num-sectors 需要恢复的扇区个数
--parallel 恢复时的并发数，可根据worker内存和ssd设置。对32G扇区，N并发至少需要N*520GiB磁盘空间
--sector-id 需要恢复的扇区id
--ticket 扇区ticket，可通过lotus-miner sectors status --on-chain-info 获取
--commR 扇区commR，用于验证恢复结果，可通过lotus-miner sectors status --on-chain-info 获取
--seal-proof-type 扇区spt，可通过lotus-miner sectors status --on-chain-info 获取
```

