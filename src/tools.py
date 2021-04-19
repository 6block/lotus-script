import os
import re
import time

local_path = os.getcwd()
files_path = os.path.abspath(os.path.join(local_path, ""))


def separate_ip(url):
    ip = re.findall(r'(?<![\.\d])(?:\d{1,3}\.){3}\d{1,3}(?![\.\d])', str(url), re.S)
    if ip:
        return ip[0]
    else:
        return None


def add(lst):
    old_list = []
    ip_list = []
    with open(files_path + '/%s.lst' % lst, 'r') as r_file:
        for l in r_file:
            if l:
                l = l.strip()
                if l[0] == '#':
                    old_list.append(l)
                    ip_list.append(l[1:])
                else:
                    ip_list.append(l)
                    l = '#' + l
                    old_list.append(l)
                print(l)
    l = '#Add New %s ' % lst.capitalize() + time.strftime("%Y%m%d", time.localtime(time.time()))
    old_list.append(l)
    with open('/home/ps/%s.lst' % lst, 'r') as r_file:
        for l in r_file:
            l = l.strip()
            if l[0] != '#':
                ip = l
                if ip not in ip_list:
                    old_list.append(ip)

    w_file = open(files_path + '/%s.lst' % lst, 'w')
    for l in old_list:
        print(l, file=w_file)
        print(l)
    w_file.close()


def deannotation(lst):
    lines = []
    with open(files_path + '/%s.lst' % lst, 'r') as r_file:
        for l in r_file:
            l = l.strip()
            lines.append(l)
    w_file = open(files_path + '/%s.lst' % lst, 'w')
    for l in lines:
        if separate_ip(l) and len(l.strip()) <= len(separate_ip(l)) + 2:
            print(separate_ip(l), file=w_file)
            print(separate_ip(l))
        else:
            print(l, file=w_file)
            print(l)
    w_file.close()


def fix(lst):
    ip_list = []
    with open(files_path + '/%s.lst' % lst, 'r') as r_file:
        for l in r_file:
            if l:
                l = l.strip()
                if l[0] == '#':
                    ip_list.append(l[1:])

    w_file = open(files_path + '/fix_%s.lst' % lst, 'w')
    for l in ip_list:
        print(l, file=w_file)
        print(l)
    w_file.close()


def move():
    os.rename('computing.lst', 'computing_old.lst')
    open('computing.lst', 'a').close()


if __name__ == "__main__":
    import sys

    lst = None
    if 'computing' in sys.argv[1]:
        lst = 'computing'
    if 'storage' in sys.argv[1]:
        lst = 'storage'
    if lst and 'add' in sys.argv[2]:
        add(lst)
    elif lst and 'de' in sys.argv[2]:
        deannotation(lst)
    elif lst and 'fix' in sys.argv[2]:
        fix(lst)
    elif 'move' in sys.argv[1]:
        move()
