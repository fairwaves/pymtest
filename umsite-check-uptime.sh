#!/bin/sh

IPS=$*

if test -z "$IPS" ; then
  echo "usage: $0 ip_address [ip_address] [ip_address] ..."
  exit 1
fi

for IP in $IPS ; do
  cat helper/umsite-check-uptime.py | ssh fairwaves@$IP "sudo python -"
  echo
done