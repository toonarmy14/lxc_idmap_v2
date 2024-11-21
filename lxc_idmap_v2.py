#!/usr/bin/env python3
import argparse
import enum
import sys


class IdType(enum.StrEnum):
    """
    Enum class to represent the type of id being mapped.
    """
    USER = 'u'
    GROUP = 'g'
    @property
    def sort_order(self):
        if self == IdType.USER:
            return 0
        return 1
    
class IdError(argparse.ArgumentTypeError):
    def __init__(self, _id: int, id_type: IdType):
        super().__init__(f'{id_type.value.upper()}ID {_id} is not in range 1-65536')
    
def create_argparser() -> argparse.ArgumentParser:
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
    return parser

def validate_ids(ids: list[tuple[IdType, int, int]]):
    _min = 1 # mapping to root user (uid=0) is not allowed
    _max = 65536
    
    for id_type, lxc_id, host_id in ids:
        if not _min <= lxc_id <= _max:
            raise IdError(lxc_id, id_type)
        
        if not _min <= host_id <= _max:
            raise IdError(host_id, id_type)
    
def create_id_lists(args:argparse.Namespace) -> list[tuple[IdType,int,int]]:
    # init empty list to hold user and group ids
    ids = []
    
    # split combined mappings and append to id lists
    for mapping in args.mappings:
        # split container ids from host ids (optional), setting host ids to default
        lxc_ids = mapping.split('=')[0]
        host_ids = mapping.split('=')[-1]
        
        # split container ids into lxc and gid (gid is optional)
        lxc_uid = lxc_ids.split(':')[0]
        lxc_gid = lxc_ids.split(':')[-1]
        
        # same splitting behavior for the host ds
        host_uid = host_ids.split(':')[0]
        host_gid = host_ids.split(':')[-1]
        
        # prefix each id with the IdType enum value
        ids.append((IdType.USER, int(lxc_uid), int(host_uid)))
        ids.append((IdType.GROUP, int(lxc_gid), int(host_gid)))
        
    # add user mappings specified by -u/--user
    for user_mapping in args.user:
        ids.append((
                IdType.USER,
                int(user_mapping.split('=')[0]),
                int(user_mapping.split('=')[-1])
        ))
        
    # add group mappings specified by -g/--group
    for group_mapping in args.group:
        ids.append((
                IdType.GROUP,
                int(group_mapping.split('=')[0]),
                int(group_mapping.split('=')[-1])
        ))
    validate_ids(ids)
    # sort ids by IdType.USER first, then in increasing order and return
    ids.sort(key=lambda x: (x[0].sort_order, x[1]))
    
    return ids

def create_default_idmap(id_type: IdType):
    return f'\nlxc.idmap = {id_type.value} 0 100000 65536'

def create_idmaps(ids: list[tuple[IdType,int,int]]) -> str|None:
    # changed k,v delimeter to `=` to be in line with lxc documentation. Calling `lxc-start` directly will fail if using `:` (as
    output: str = ''
    prev_id: int = 0
    previous_id_type: IdType|None = None
    
    # handle case where no user mappings are specified
    if ids[0][0] == IdType.GROUP:
        output += create_default_idmap(IdType.USER)
        
    for idx, (id_type, lxc_id, host_id) in enumerate(ids):
        # 1. set vars for mapping preceeding id ranges
        if previous_id_type is not None and id_type != previous_id_type:
            rng = 65536 - prev_id
            output += f"\nlxc.idmap = u {prev_id} {prev_id + 100000} {rng}"
            prev_id = 0
            previous_id_type = id_type
        rng = lxc_id - prev_id
        # ensure not None
        if previous_id_type is None:
            previous_id_type = id_type

        output += f"\nlxc.idmap = {previous_id_type.value} {prev_id} {prev_id + 100000} {rng}"
        
        # 2. map the current id
        output += f"\nlxc.idmap = {id_type.value} {lxc_id} {host_id} 1"
        
        # 3. update previous id and type
        prev_id = lxc_id + 1 # increment previous id by 1 to account for new mapping
        previous_id_type = id_type
        
    # finish mapping to 65536
    output += f'\nlxc.idmap = {previous_id_type.value} {prev_id} {prev_id + 100000} {65536 - prev_id}'
    
    # in case of no group mappings, group mapping is still required to be explicitly mapped in conf file
    if previous_id_type ==IdType.USER.value:
        output += create_default_idmap(IdType.GROUP)
    return output


def create_conf_content(ids: list[tuple[IdType,int,int]], ctid: int = None):
    conf_content = f"\n# Add to /etc/pve/lxc/{ctid or '<container_id>'}.conf:"
    conf_content += create_idmaps(ids)
    return conf_content

def create_subuid_subgid_info(ids: list[tuple[IdType,int,int]]):
    """
     Method to create the lines needed to be added to /etc/sub{u,g}id on the host
     This is necessary because root on host creates the container and is responsible
      for implementing the idmappings
    """
    
    user_ids = [uid for (id_type, _, uid) in ids if id_type == IdType.USER]
    group_ids = [gid for (id_type, _, gid) in ids if id_type == IdType.GROUP]
    
    output = '\n\n# Add to /etc/subuid:'
    for uid in user_ids:
        output += f"\nroot:{uid}:1"
    output += '\n\n# Add to /etc/subgid:'
    for gid in group_ids:
        output += f"\nroot:{gid}:1"
        
    return output


def validate_args():
    if len(sys.argv) == 1:
        sys.exit("No arguments provided. Please provide at least one argument.")


def main():
    parser = create_argparser()
    args = parser.parse_args()
    validate_args() # ensures that at least one argument is provided
    ids = create_id_lists(args)
    output=''
    output += create_conf_content(ids)
    output += create_subuid_subgid_info(ids)
    print(output)

if __name__ == "__main__":
    main()
