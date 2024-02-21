# lxc_idmapper
Little python script to provide the $CTID.conf, /etc/subuid, and /etc/subgid mappings for unprivileged lxcs.

All arguments can be used together.
Don't duplicate use of the same id, I don't have any handling to skip over that, so the config will be invalid...

Positional Argument syntax
lxc_uid[:lxc_gid][=host_uid[:host_gid]]

- Separate multiple id mappings with a <space>
- only the container users id is required.
- if no container group id then it will be set to the user id  
- if no host user id is provided, it will be set to the container user id. 
- if no host group id is provided, it will be set to the host user id. 