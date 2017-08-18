#!/usr/bin/python
#coding=utf-8

from hosts import HostsUpdater,DefaultHosts,ZipHosts

def main():
	#hosts更新器
	hostsUpdater = HostsUpdater()
	#传入hosts文件所在地
	#AD
	hostsUpdater.put(DefaultHosts(r'https://raw.githubusercontent.com/vokins/yhosts/master/hosts'))
	hostsUpdater.put(DefaultHosts(r'https://raw.githubusercontent.com/neoFelhz/neohosts/master/nadhost'))
	#GFW
	hostsUpdater.put(DefaultHosts(r'https://raw.githubusercontent.com/racaljk/hosts/master/hosts'))
	hostsUpdater.put(DefaultHosts(r'https://raw.githubusercontent.com/sy618/hosts/master/FQ'))
	hostsUpdater.put(DefaultHosts(r'https://raw.githubusercontent.com/sy618/hosts/master/y'))
	hostsUpdater.put(DefaultHosts(r'https://raw.githubusercontent.com/sy618/hosts/master/p'))
	hostsUpdater.put(ZipHosts(r'https://4nn.net/download/hosts/hosts.zip',hosts_path='hosts/hosts',decode='gbk'))
	#开始更新
	hostsUpdater.update()

if __name__ == '__main__':
	main()