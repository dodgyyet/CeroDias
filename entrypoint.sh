#!/bin/bash
set -e

# Wait for Flask app to write the public key (shared volume)
echo "Waiting for public key..."
for i in $(seq 1 30); do
    if [ -f /tmp/cerodias/id_rsa.pub ]; then
        break
    fi
    sleep 2
done

if [ ! -f /tmp/cerodias/id_rsa.pub ]; then
    echo "WARNING: public key not found after 60s, starting anyway"
fi

# Set up authorized_keys for svc_admin
mkdir -p /home/svc_admin/.ssh
if [ -f /tmp/cerodias/id_rsa.pub ]; then
    cp /tmp/cerodias/id_rsa.pub /home/svc_admin/.ssh/authorized_keys
    chmod 700 /home/svc_admin/.ssh
    chmod 600 /home/svc_admin/.ssh/authorized_keys
    chown -R svc_admin:svc_admin /home/svc_admin/.ssh
fi

# Ensure sshd host keys exist
ssh-keygen -A

# Start SSH daemon
exec /usr/sbin/sshd -D -e
