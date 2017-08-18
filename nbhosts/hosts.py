#!/usr/bin/python
#coding=utf-8
from urllib import request
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
from abc import ABC, abstractmethod
import telnetlib
import re
import time
import tempfile
import os
import platform

#HostsUrl类，若无法直接获得url则使用该类进行封装处理过程
class HostsUrl(ABC):
	#获取url地址
	@abstractmethod
	def get_url(self):
		pass

#抽象Hosts类
class Hosts(ABC):
	#ip domain正则对象,只保留ipv4地址
	_check_pattern = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) +(.+)$')

	#解码body返回domain ip的dict
	@classmethod
	def _decode(cls,body):
		hosts=dict()
		#格式body
		body = body.replace('\r\n','\n')
		body = body.replace('\r','\n')
		body = body.replace('\t',' ')
		pattern = re.compile(r' {2,}')
		body = pattern.sub(' ',body)
		#以行分割
		content  =body.split('\n')

		for line in content:
			#去除两边空格
			line=line.strip()
			#ip domain正则匹配
			matcher=cls._check_pattern.match(line)
			if matcher==None:
				continue
			else:
				if matcher.group(2)=='localhost' or matcher.group(2)=='ip6-localhost' or matcher.group(2)=='ip6-loopback':
					continue
				else:
					hosts[matcher.group(2)]=matcher.group(1)	
		return hosts

	#获取文件
	@staticmethod
	def _get_file(url,timeout):
		#判断是否是本地文件
		is_file=os.path.isfile(url)
		if is_file:
			with open(url,'rb') as file:
				return file.read()
		else:
			req=request.Request(url);
			req.add_header("User-Agent","Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36")
			with request.urlopen(req,timeout=timeout) as response:
				return response.read()

	#获取hosts
	@abstractmethod
	def get_hosts(self):
		pass

#默认hosts
class DefaultHosts(Hosts):
	def __init__(self, url, decode='utf-8', timeout=60):
		self.url=url
		self.decode=decode
		self.timeout=timeout
	
	def get_hosts(self):

		#获取真正url
		try:
			if isinstance(self.url,HostsUrl):
				self.url=self.url.get_url()
		except Exception as e:
			print('source fail('+str(e)+'): '+str(self.url.__class__))
			return dict()

		print('source: '+self.url)

		try:
			body = self._get_file(self.url,self.timeout).decode(self.decode)
		except Exception as e:
			print('fail('+str(e)+'): '+self.url)
			return dict()
		hosts=self._decode(body)
		print('done: '+self.url)
		return hosts

#zip文件hosts
class ZipHosts(Hosts):
	#zip文件下载的临时文件夹
	_tmp_dir = tempfile.TemporaryDirectory(prefix='tmphosts_',dir='./')

	def __init__(self, url, hosts_path,zip_password=None, decode='utf-8', timeout=60):
		self.url=url
		self.hosts_path = hosts_path
		self.zip_password=zip_password
		self.decode=decode
		self.timeout=timeout
	
	def get_hosts(self):

		#获取真正url
		try:
			if isinstance(self.url,HostsUrl):
				self.url=self.url.get_url()
		except Exception as e:
			print('source fail('+str(e)+'): '+str(self.url.__class__))
			return dict()

		print('source: '+self.url)

		try:
			#下载写入临时文件
			with tempfile.TemporaryFile(prefix='tmpzip_',dir=self._tmp_dir.name) as tmp_zip:
				tmp_zip.write(self._get_file(self.url,self.timeout))
				#读取下载好的zip文件
				with ZipFile(tmp_zip,'r') as zip:
					zipinfo=zip.getinfo(self.hosts_path)
					#将hosts文件解压到临时目录
					with tempfile.TemporaryDirectory(prefix='tmpzip_dir_',dir='./') as tmp_zip_dir:
						zip.extract(zipinfo,path=tmp_zip_dir,pwd=self.zip_password.encode() if self.zip_password!=None else None)
						#读取文件内容
						with open(tmp_zip_dir+'/'+self.hosts_path,'rb') as file:
							body=file.read().decode(self.decode)
		except Exception as e:
				print('fail('+str(e)+'): '+self.url)
				return dict()
		hosts=self._decode(body)
		print('done: '+self.url)
		return hosts

#hosts更新器
class HostsUpdater:
	def __init__(self,begin_tag=r'# Modified Hosts Start',end_tag=r'# Modified Hosts End',ping_timeout=3,ping_thread_count=512):
		self.hosts_list=[]
		self.begin_tag=begin_tag
		self.end_tag=end_tag
		self.ping_timeout=ping_timeout
		self.ping_thread_count=ping_thread_count
		self.platsys=platform.system()
	
	def put(self,hosts):
		self.hosts_list.append(hosts)
	
	def update(self):
		print("正在下载hosts文件...")
		#批量启动线程下载hosts
		with ThreadPoolExecutor(len(self.hosts_list)) as executor:
			future_list=[]
			for hosts in self.hosts_list:
				future_list.append(executor.submit(hosts.get_hosts))
			hosts_content_list=[]
			for future in future_list:
				hosts_content_list.append(future.result())
		print("检查ip是否有效...")
		#去除重复,创建ip集合和对应域的ip集合
		ips=set()
		domains=dict()
		for hosts_item in hosts_content_list:
			for key,val in hosts_item.items():
				if not self.__is_ignore_ip(val):
					ips.add(val)
				if key in domains.keys():
					domains[key].add(val)
				else:
					domains[key]=set({val})
		ip_check=self.__check_ips(ips)
		
		print("合并hosts文件...")
		hosts=dict()
		for key,val in domains.items():
			#找到最小延迟的ip
			domain_ips=list(val)
			min_delay_ip=domain_ips[0]
			ignore_ip=False
			for ip in domain_ips:
				#如果是忽略ip则直接退出
				if self.__is_ignore_ip(ip):
					hosts[key]=ip
					ignore_ip=True
					break
				if ip_check[min_delay_ip]==None:
					min_delay_ip=ip
				elif ip_check[ip]!=None and ip_check[ip]<ip_check[min_delay_ip]:
					min_delay_ip=ip
			if ignore_ip==False and ip_check[min_delay_ip]!=None:
				hosts[key]=min_delay_ip

		#创建hosts内容
		hosts_data = '\n'
		hosts_data += '# Localhost (DO NOT REMOVE) Start\n'
		hosts_data += '127.0.0.1	localhost\n'
		hosts_data += '::1	localhost\n'
		hosts_data += '::1	ip6-localhost\n'
		hosts_data += '::1	ip6-loopback\n'
		hosts_data += '# Localhost (DO NOT REMOVE) End\n\n'
		for key,val in hosts.items():
			hosts_data += val+' '+key+'\n'
		hosts_data += '\n'

		print("写入本地hosts文件...")
		#获取当前系统的hosts文件路径
		if self.platsys=='Windows':
			hosts_path=r'C:/Windows/System32/drivers/etc/hosts'
		elif self.platsys=='Linux':
			hosts_path=r'/etc/hosts'
		start_flag=False#是否找到开始标志
		write_flag=False#是否已经写入新的hosts
		new_hosts=''
		with open(hosts_path,'r') as file:
			for line in file:
				if self.begin_tag in line:
					#是否找到起始标志
					start_flag=True
					new_hosts+=line
				elif self.end_tag in line:
					#是否找到结束标志
					start_flag=False
				if start_flag==True:
					if write_flag==False:
						new_hosts+=hosts_data
						write_flag=True
				else:
					new_hosts+=line
		#没有找到结束标志
		if start_flag==True:
			print("写入本地hosts文件失败,hosts文件缺少结束标志!")
			return
		#没有找到开始标志，则写入末尾
		if write_flag==False:
			new_hosts+='\n\n'+self.begin_tag+'\n'
			new_hosts+=hosts_data
			new_hosts+=self.end_tag+'\n'
		#写入本地hosts
		new_hosts.encode("utf-8")
		with open(hosts_path,'w') as file:
			file.write(new_hosts)
		#刷新hosts
		if self.platsys=='Windows':
			os.popen(r'ipconfig /flushdns')
		elif self.platsys=='Linux':
			os.popen(r'/etc/init.d/networking restart')
		print("hosts文件更新完毕!")
	
	#检查ip集合并返回ip是否有效的字典
	def __check_ips(self,ips):
		ip_check=dict()
		#多线程ping ip
		with ThreadPoolExecutor(self.ping_thread_count) as executor:
			future_dict=dict()
			for ip in ips:
				future_dict[ip]=executor.submit(self.__check_ip,ip,self.ping_timeout)
			for ip,future in future_dict.items():
				ip_check[ip]=future.result()
		return ip_check

	#检查ip 443端口是否可连接
	@staticmethod
	def __check_ip(ip,timeout):
		delay=0
		fail=0
		for i in range(4):
			try:
				begin=time.time()
				tn = telnetlib.Telnet(ip, port=443, timeout=timeout)
				end= time.time()
				tn.close()
				delay+=end-begin
			except Exception as e:
				delay+=timeout
				fail+=1
		if fail==4:
			return None
		else:
			return delay


	#判断ip被忽略的
	@staticmethod
	def __is_ignore_ip(ip):
		if ip=='127.0.0.1' or ip=='0.0.0.0':
			return True
		else:
			return False