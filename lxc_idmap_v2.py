#!/usr/bin/env python3
import argparse

def create_argparser():
    # Create the parser
    parser = argparse.ArgumentParser(description='Simple python tool to provide user id mappings for unprivileged LXCs on Proxmox.')
    
    parser.add_argument('mappings',
                        metavar='lxc_uid[:lxc_gid][=host_uid[:host_gid]]',
                        nargs='*',
                        default=[],
                        help='Container uid and optional gid to map to host. If a gid is not specified, the uid will be used for the gid value, unless `-U/--user` is passed as .')
    
    # Add the --user argument
    parser.add_argument('-u', '--user',
                        nargs='?',
                        action='append',
                        default=[],
                        help='accepts a single container user id (ex. `-u 1000`), or container user id and host user id pair separated by equals sign (ex `-u 1000=107`). '
                             'if no host id specified, it will be set as the same as the container id. `-u 1000` is equivalent to `-u 1000=1000`. '
                             '*NO associated gid mapping will be created. If this behavior is desired, siomply specify the id without the -u/--user flag (ex: `lxc_idmapper 1000` is equivalent to `lxc-idmapper -u 1000 -g 1000`')
    
    
    parser.add_argument('-g', '--group',
                        nargs='?',
                        action='append',
                        default=[],
                        help='accepts a single container group id (ex. `-g 1000`), or container group id and host group id pair separated by equals sign (ex `-g 1000=107`). '
                             'if no host id specified, it will be set as the same as the container id. `-u 1000` is equivalent to `-u 1000=1000`. '
                             'No associated user id/uid mapping will be created.')
    return parser.parse_args()

def validate_ids(user_ids, group_ids):
    min = 1
    max = 65536
    for lxc_id, host_id in user_ids:
        if not min <= lxc_id <= max:
            raise argparse.ArgumentTypeError(f'UID {lxc_id} is not in range {min}-{max}')
        elif not min <= host_id <= max:
            raise argparse.ArgumentTypeError(f'UID {host_id} is not in range {min}-{max}')
            
    for lxc_id, host_id in group_ids:
        if not min <= lxc_id <= max:
            raise argparse.ArgumentTypeError(f'UID {lxc_id} is not in range {min}-{max}')
        elif not min <= host_id <= max:
            raise argparse.ArgumentTypeError(f'UID {host_id} is not in range {min}-{max}')
    
def create_id_lists(args):
    # init empty lists to hold user and group ids
    
    user_ids, group_ids = [],[]
    
    for mapping in args.mappings:
        if '=' in mapping:
                lxc_ids = mapping.split('=')[0]
                host_ids = mapping.split('=')[1]
        else:
            # set both lxc and host ids to mapping argument
            lxc_ids = host_ids = mapping
        
        if ':' in lxc_ids:
            lxc_uid = lxc_ids.split(':')[0]
            lxc_gid = lxc_ids.split(':')[1]
        else:
            # no group id passed. set to same value as user id
            lxc_uid = lxc_gid = lxc_ids
        
        # same splitting behavior for host_ids
        if ':' in host_ids:
            host_uid = host_ids.split(':')[0]
            host_gid = host_ids.split(':')[1]
        else:
            # no group id passed. set to same value as user id
            host_uid = host_ids
            host_gid = lxc_gid
        
        user_ids.append((int(lxc_uid), int(host_uid)))
        group_ids.append((int(lxc_gid), int(host_gid)))
        
    
    for user_mapping in args.user:
        lxc_uid = user_mapping.split('=')[0]
        host_uid = user_mapping.split('=')[-1]
        user_ids.append((int(lxc_uid), int(host_uid)))
        
    for group_mapping in args.group:
        lxc_gid = group_mapping.split('=')[0]
        host_gid = group_mapping.split('=')[-1]
        group_ids.append((int(lxc_gid), int(host_gid)))
    
    validate_ids(user_ids, group_ids)
    # sort ids in increasing order and return
    return sorted(user_ids, key=lambda x: x[0]), sorted(group_ids, key=lambda x: x[0])

def create_idmaps(ids: list[tuple[int,int]], kind:str):
    output = ''
    for idx, (lxc_id, host_id) in enumerate(ids):
        if idx == 0:
            output += f"lxc.idmap: {kind} 0 100000 {lxc_id}\n"
        else:
            prev_id = ids[idx - 1][0]
            output += f"lxc.idmap: {kind} {prev_id + 1}  {prev_id + 100001} {(lxc_id - 1) - prev_id}\n"
        
        output += f"lxc.idmap: {kind} {lxc_id}  {host_id} 1\n"
    
    last_id = ids[-1][0]
    output += f'lxc.idmap: {kind} {last_id + 1} {last_id + 100001}  {65535 - last_id}\n'
    return output

def create_conf_content(user_ids, group_ids):
    conf_content = "\n# Add to /etc/pve/lxc/<container_id>.conf:\n"
    conf_content += create_idmaps(user_ids, "u")
    conf_content += create_idmaps(group_ids, "g")
    return conf_content

def create_subuid_subgid_info(user_ids, group_ids):
    output = '\n# Add to /etc/subuid:\n'
    for _, uid in user_ids:
        output += f"root:{uid}:1\n" # root access to host uid needed for lxc creation (since root creates the lxc)
    output += '\n# Add to /etc/subgid:\n'
    for _, gid in group_ids:
        output += f"root:{gid}:1\n"
        
    return output

def main():
    args = create_argparser()
    user_ids, group_ids = create_id_lists(args)
    output=''
    output += create_conf_content(user_ids, group_ids)
    output += create_subuid_subgid_info(user_ids, group_ids)
    print(output)

if __name__ == "__main__":
    main()
