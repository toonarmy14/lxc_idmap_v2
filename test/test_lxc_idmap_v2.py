import argparse
import sys
import unittest
from io import StringIO
from textwrap import dedent
from unittest import mock

from lxc_idmap_v2 import (
    IdType,
    IdError,
    create_argparser,
    validate_ids,
    create_id_lists,
    create_idmaps,
    create_conf_content,
    create_subuid_subgid_info,
    main,
)


class TestLxcIdmapper(unittest.TestCase):
    
    def test_create_id_lists_single_mapping(self):
        args=argparse.Namespace(
                mappings=['1000'],
                user=[],
                group=[]
        )
        ids=create_id_lists(args)
        self.assertEqual(ids, [(IdType.USER, 1000, 1000), (IdType.GROUP, 1000, 1000)])
    
    def test_create_id_lists_mapping_with_host_id(self):
        args=argparse.Namespace(
                mappings=['1000=2000'],
                user=[],
                group=[]
        )
        ids=create_id_lists(args)
        expected_output=[
                (IdType.USER, 1000, 2000),
                (IdType.GROUP, 1000, 2000)
        ]
        self.assertEqual(ids, expected_output)
    
    def test_create_id_lists_mapping_with_uid_gid(self):
        args=argparse.Namespace(
                mappings=['1000:1001=2000:2001'],
                user=[],
                group=[]
        )
        ids=create_id_lists(args)
        expected_output=[
                (IdType.USER, 1000, 2000),
                (IdType.GROUP, 1001, 2001)
        ]
        self.assertEqual(ids, expected_output)
    
    def test_create_id_lists_with_user_option(self):
        args=argparse.Namespace(
                mappings=[],
                user=['1000'],
                group=[]
        )
        ids=create_id_lists(args)
        expected_output=[
                (IdType.USER, 1000, 1000)
        ]
        self.assertEqual(ids, expected_output)
    
    def test_create_id_lists_with_user_host_id(self):
        args=argparse.Namespace(
                mappings=[],
                user=['1000=2000'],
                group=[]
        )
        ids=create_id_lists(args)
        expected_output=[
                (IdType.USER, 1000, 2000)
        ]
        self.assertEqual(ids, expected_output)
    
    def test_validate_ids_valid_ids(self):
        user_ids=[(1000, 1000), (2000, 2000)]
        group_ids=[(1000, 1000)]
        ids=[
                (IdType.USER, 1000, 1000),
                (IdType.USER, 2000, 2000),
                (IdType.GROUP, 1000, 1000)]
        try:
            validate_ids(ids)
        except IdError:
            self.fail("validate_ids() raised ArgumentTypeError unexpectedly!")
    
    def test_validate_ids_invalid_ids(self):
        ids=[(IdType.USER, 0, 1000)]
        with self.assertRaises(IdError):
            validate_ids(ids)
    
    def test_create_idmaps_single_id(self):
        ids=[(IdType.USER, 1000, 1000)]
        expected_output=(
                "lxc.idmap = u 0 100000 1000\n"
                "lxc.idmap = u 1000 1000 1\n"
                "lxc.idmap = u 1001 101001 64535\n"
                "lxc.idmap = g 0 100000 65536\n"
        )
        output=create_idmaps(ids)
        self.assertEqual(output.strip(), expected_output.strip())
    
    def test_create_conf_content(self):
        ids=[(IdType.USER, 1000, 1000),
             (IdType.GROUP, 1000, 1000)]
        output=create_conf_content(ids)
        expected_output=\
                ("# Add to /etc/pve/lxc/<container_id>.conf:\n"
                "lxc.idmap = u 0 100000 1000\n"
                "lxc.idmap = u 1000 1000 1\n"
                "lxc.idmap = u 1001 101001 64535\n"
                "lxc.idmap = g 0 100000 1000\n"
                "lxc.idmap = g 1000 1000 1\n"
                "lxc.idmap = g 1001 101001 64535\n")
        self.assertEqual(output.strip(), expected_output.strip())
    
    def test_create_subuid_subgid_info(self):
        ids=[(IdType.USER, 1000, 1000),
             (IdType.GROUP, 1000, 1000)]
        output=create_subuid_subgid_info(ids)
        expected_output=(
                "# Add to /etc/subuid:\n"
                "root:1000:1\n"
                "\n"
                "# Add to /etc/subgid:\n"
                "root:1000:1\n"
        )
        self.assertEqual(output.strip(), expected_output.strip())
    
    def test_main_output(self):
        original_stdout=sys.stdout
        original_argv=sys.argv
        try:
            sys.argv=['lxc_idmap_v2', '1000']
            sys.stdout=StringIO()
            main()
            output=sys.stdout.getvalue().strip()
            expected_output=(
                    "# Add to /etc/pve/lxc/<container_id>.conf:\n"
                    "lxc.idmap = u 0 100000 1000\n"
                    "lxc.idmap = u 1000 1000 1\n"
                    "lxc.idmap = u 1001 101001 64535\n"
                    "lxc.idmap = g 0 100000 1000\n"
                    "lxc.idmap = g 1000 1000 1\n"
                    "lxc.idmap = g 1001 101001 64535\n"
                    "\n"
                    "# Add to /etc/subuid:\n"
                    "root:1000:1\n"
                    "\n"
                    "# Add to /etc/subgid:\n"
                    "root:1000:1"
            )
            self.assertEqual(output, expected_output)
        finally:
            sys.stdout=original_stdout
            sys.argv=original_argv
    
    def test_create_id_lists_single_host_id_mapping(self):
        """
        ensure that a single host id mapping is correctly mapped to both user and group ids
        """
        args=argparse.Namespace(
                mappings=['1000:2000=3000'],
                user=[],
                group=[]
        )
        ids=create_id_lists(args)
        expected_output=[
                (IdType.USER, 1000, 3000),
                (IdType.GROUP, 2000, 3000)
        ]
        self.assertEqual(ids, expected_output)
        
    def test_create_id_lists_single_host_id_mapping_with_control(self):
        """
        ensure that a single host id mapping is correctly mapped to both user and group ids.
        Runs two tests, witht the first one specifying both user and group ids for
        the host id mapping, and the second one specifying only the user id for the
        host id mapping - testing that the output is equivalent.
        """
        control_args=argparse.Namespace(
                mappings=['1000:2000=3000:3000'],
                user=[],
                group=[]
        )
        test_args=argparse.Namespace(
                mappings=['1000:2000=3000'],
                user=[],
                group=[]
        )
        control_ids=create_id_lists(control_args)
        expected_output=[
                (IdType.USER, 1000, 3000),
                (IdType.GROUP, 2000, 3000)
        ]
        self.assertEqual(control_ids, expected_output)
        
        test_ids=create_id_lists(test_args)
        self.assertEqual(test_ids, control_ids)
        
    
    def test_create_id_lists_with_all_options(self):
        args=argparse.Namespace(
                mappings=['1000:2000=3000:4000'],
                user=['5000=6000'],
                group=['7000=8000']
        )
        ids=create_id_lists(args)
        expected_output=[
                (IdType.USER, 1000, 3000),
                (IdType.USER, 5000, 6000),
                (IdType.GROUP, 2000, 4000),
                (IdType.GROUP, 7000, 8000)
        ]
        self.assertEqual(ids, expected_output)
        
    def test_alternate_equivalent_argument_formats(self):
        # Test equivalent output with what should be equivalent inputs
        control_args=argparse.Namespace(
                mappings=['1000:2000=3000:4000'],
                user=['5000=6000'],
                group=['7000=8000']
        )
        control_ids=create_id_lists(control_args)
        alt_args=argparse.Namespace(
                mappings=[],
                user=['1000=3000', '5000=6000'],
                group=['2000=4000', '7000=8000']
        )
        alt_ids=create_id_lists(alt_args)
        self.assertEqual(control_ids, alt_ids)
        
    def test_sorting_of_output_by_placing_larger_id_first(self):
        # Test sorting of output by placing larger id first
        args=argparse.Namespace(
                mappings=[],
                user=['5000=6000', '1000=3000'],
                group=['7000=8000', '2000=4000']
        )
        
        ids=create_id_lists(args)
        
        expected_output=[
                (IdType.USER, 1000, 3000),
                (IdType.USER, 5000, 6000),
                (IdType.GROUP, 2000, 4000),
                (IdType.GROUP, 7000, 8000)
        ]
        self.assertEqual(ids, expected_output)
        
    
    def test_create_id_lists_multiple_mappings(self):
        args=argparse.Namespace(
                mappings=['1000:2000=3000:4000', '5000:6000=7000:8000'],
                user=['9000=10000'],
                group=['11000=12000']
        )
        ids=create_id_lists(args)
        expected_output=[
                (IdType.USER, 1000, 3000),
                (IdType.USER, 5000, 7000),
                (IdType.USER, 9000, 10000),
                (IdType.GROUP, 2000, 4000),
                (IdType.GROUP, 6000, 8000),
                (IdType.GROUP, 11000, 12000)
        ]
        self.assertEqual(ids, expected_output)
    
    def test_validate_ids_lxc_user_id_exceeds_max(self):
        ids=[(IdType.USER, 1000, 1000), (IdType.USER, 70000, 70000)]
        with self.assertRaises(IdError):
            validate_ids(ids)
    
    def test_validate_ids_lxc_group_id_exceeds_max(self):
        ids=[(IdType.GROUP, 1000, 1000), (IdType.GROUP, 70000, 70000)]
        with self.assertRaises(IdError):
            validate_ids(ids)
    
    def test_validate_ids_lxc_user_id_below_min(self):
        ids=[(IdType.USER, 0, 1000)]
        with self.assertRaises(IdError):
            validate_ids(ids)
    
    def test_validate_ids_lxc_group_id_below_min(self):
        ids=[(IdType.GROUP, 0, 1000)]
        with self.assertRaises(IdError):
            validate_ids(ids)
    
    def test_main_with_complex_arguments(self):
        original_stdout=sys.stdout
        original_argv=sys.argv
        try:
            sys.argv=[
                    'lxc-idmap-v2',
                    '1000:2000=3000:4000',
                    '-u', '5000=6000',
                    '-g', '7000=8000'
            ]
            sys.stdout=StringIO()
            main()
            output=sys.stdout.getvalue().strip()
            expected_output_start=(
                    "# Add to /etc/pve/lxc/<container_id>.conf:\n"
            )
            self.assertTrue(output.startswith(expected_output_start))
            # Additional checks can be added to verify the content
        finally:
            sys.stdout=original_stdout
            sys.argv=original_argv
            
    def test_main_with_complex_arguments_alt_flags(self):
        original_stdout=sys.stdout
        original_argv=sys.argv
        try:
            sys.argv=[
                    'lxc-idmap-v2',
                    '1000:2000=3000:4000',
                    '--user', '5000=6000',
                    '--group', '7000=8000'
            ]
            sys.stdout=StringIO()
            main()
            output=sys.stdout.getvalue().strip()
            expected_output_start=(
                    "# Add to /etc/pve/lxc/<container_id>.conf:\n"
            )
            self.assertTrue(output.startswith(expected_output_start))
            # Additional checks can be added to verify the content
        finally:
            sys.stdout=original_stdout
            sys.argv=original_argv
    
    def test_main_with_invalid_id(self):
        original_argv=sys.argv
        ids = ['70000', '-1', '0', '65537']
        for _id in ids:
            try:
                sys.argv=['lxc-idmap-v2', _id]
                with self.assertRaises(IdError):
                    main()
            finally:
                sys.argv=original_argv
        
    def test_create_idmaps_multiple_ids(self):
        ids=[(IdType.USER, 1000, 1000),
             (IdType.USER, 2000, 2000),
             (IdType.USER, 3000, 3000)]
        output=create_idmaps(ids)
        # Verify that the output contains mappings for all IDs
        self.assertIn('lxc.idmap = u 1000 1000 1', output)
        self.assertIn('lxc.idmap = u 2000 2000 1', output)
        self.assertIn('lxc.idmap = u 3000 3000 1', output)
    
    def test_create_conf_content_with_multiple_ids(self):
        ids=[(IdType.USER, 1000, 1000),
             (IdType.USER, 2000, 2000),
             (IdType.USER, 3000, 3000),
             (IdType.GROUP, 4000, 4000),
             (IdType.GROUP, 5000, 5000)]
        output=create_conf_content(ids)
        # Check that all IDs are present in the output
        for id_type, uid, host_uid in ids:
            if id_type == IdType.USER:
                self.assertIn(f"lxc.idmap = u {uid} {host_uid} 1", output)
            elif id_type == IdType.GROUP:
                self.assertIn(f"lxc.idmap = g {uid} {host_uid} 1", output)
    
    def test_create_subuid_subgid_info_with_multiple_ids(self):
        ids=[(IdType.USER, 1000, 1000),
             (IdType.USER, 2000, 2000),
             (IdType.GROUP, 3000, 3000),
             (IdType.GROUP, 4000, 4000)]
        output=create_subuid_subgid_info(ids)
        for _, _, host_id in ids:
            self.assertIn(f"root:{host_id}:1", output)
    
    def test_create_argparser_with_all_options(self):
        test_args=[
                'lxc-idmap-v2',
                '1000:2000=3000:4000',
                '-u', '5000=6000',
                '-g', '7000=8000'
        ]
        with unittest.mock.patch('sys.argv', test_args):
            parser=create_argparser()
            args=parser.parse_args()
            self.assertEqual(args.mappings, ['1000:2000=3000:4000'])
            self.assertEqual(args.user, ['5000=6000'])
            self.assertEqual(args.group, ['7000=8000'])
    
    def test_create_argparser_missing_values(self):
        test_args=['lxc-idmap-v2']
        with unittest.mock.patch('sys.argv', test_args):
            parser=create_argparser()
            args=parser.parse_args()
            self.assertEqual(args.mappings, [])
            self.assertEqual(args.user, [])
            self.assertEqual(args.group, [])
    
    def test_main_with_no_arguments(self):
        original_stdout=sys.stdout
        original_argv=sys.argv
        original_stderr=sys.stderr
        try:
            sys.argv=['lxc-idmap-v2']
            sys.stdout=StringIO()
            sys.stderr=StringIO()
            with self.assertRaises(SystemExit):
                # no arguments provided causes sys.exit() to be called
                main()
        finally:
            sys.stdout=original_stdout
            sys.stderr=original_stderr
            sys.argv=original_argv
            
    def test_main_with_all_arguments(self):
        original_stdout=sys.stdout
        original_argv=sys.argv
        sys.argv=['lxc-idmap-v2', '-u', '1000=2000', '-g', '3000=4000', '--group', '3333=4444', '-g', '111', '--user', '5000=6000', '--group', '7000=8000']
        sys.stdout=StringIO()
        expected_output=dedent("""\
        
        # Add to /etc/pve/lxc/<container_id>.conf:
        lxc.idmap = u 0 100000 1000
        lxc.idmap = u 1000 2000 1
        lxc.idmap = u 1001 101001 3999
        lxc.idmap = u 5000 6000 1
        lxc.idmap = u 5001 105001 60535
        lxc.idmap = g 0 100000 111
        lxc.idmap = g 111 111 1
        lxc.idmap = g 112 100112 2888
        lxc.idmap = g 3000 4000 1
        lxc.idmap = g 3001 103001 332
        lxc.idmap = g 3333 4444 1
        lxc.idmap = g 3334 103334 3666
        lxc.idmap = g 7000 8000 1
        lxc.idmap = g 7001 107001 58535
        
        # Add to /etc/subuid:
        root:2000:1
        root:6000:1
        
        # Add to /etc/subgid:
        root:111:1
        root:4000:1
        root:4444:1
        root:8000:1
        """)
        main()
        output=sys.stdout.getvalue()
        self.assertEqual(output, expected_output)
        sys.stdout=original_stdout
        sys.argv=original_argv


if __name__ == '__main__':
    unittest.main()
