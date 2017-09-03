#!/bin/sh

IPS=$*

export SSHPASS=fairwaves

if test -z "$IPS" ; then
  echo "usage: $0 ip_address [ip_address] [ip_address] ..."
  exit 1
fi

ssh-keygen -R ${IP} >/dev/null 2>&1

for IP in $IPS ; do
  cat helper/umsite-check-uptime.py | sshpass -e ssh -o "StrictHostKeyChecking no" fairwaves@$IP "sudo python -"
  echo
done