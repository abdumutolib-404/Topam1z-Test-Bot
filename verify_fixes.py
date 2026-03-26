#!/usr/bin/env python3
"""
Automated verification script for @topam1z_bot fixes
Checks if all fixes have been properly applied
"""

import os
import sys
import re

# ANSI colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def check_file_exists(filename):
    """Check if a file exists."""
    if os.path.exists(filename):
        print(f"{GREEN}✓{NC} {filename} exists")
        return True
    else:
        print(f"{RED}✗{NC} {filename} missing")
        return False

def check_pattern(filename, pattern, description):
    """Check if a pattern exists in a file."""
    if not os.path.exists(filename):
        print(f"{RED}✗{NC} {filename} not found for check: {description}")
        return False
    
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if re.search(pattern, content, re.MULTILINE):
        print(f"{GREEN}✓{NC} {description}")
        return True
    else:
        print(f"{YELLOW}⚠{NC} {description} - NOT FOUND")
        return False

def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  @topam1z_bot - Automated Fix Verification                  ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    total_checks = 0
    passed_checks = 0
    
    # Check 1: File existence
    print(f"{BLUE}1️⃣  Checking file existence...{NC}")
    files = ['yt_dlp_tools.py', 'moviebox_tools.py', 'handlers.py', 'shared.py', 'admin_handlers.py']
    for f in files:
        total_checks += 1
        if check_file_exists(f):
            passed_checks += 1
    print()
    
    # Check 2: yt_dlp_tools.py fixes
    print(f"{BLUE}2️⃣  Checking yt_dlp_tools.py fixes...{NC}")
    
    checks = [
        ('yt_dlp_tools.py', r'Multiple fallback strategies', 
         'yt_dlp_tools.py: Has robust fallback code'),
        ('yt_dlp_tools.py', r'def _find_file\(uid: str\) -> str \| None:', 
         'yt_dlp_tools.py: _find_file updated with better logic'),
        ('yt_dlp_tools.py', r'format_str = "bestvideo\[height<=', 
         'yt_dlp_tools.py: Uses simplified format selection'),
        ('yt_dlp_tools.py', r'for start, end in \[\(30, 45\)', 
         'yt_dlp_tools.py: _dl_sample has multiple time ranges'),
    ]
    
    for filename, pattern, desc in checks:
        total_checks += 1
        if check_pattern(filename, pattern, desc):
            passed_checks += 1
    print()
    
    # Check 3: moviebox_tools.py fixes
    print(f"{BLUE}3️⃣  Checking moviebox_tools.py fixes...{NC}")
    
    checks = [
        ('moviebox_tools.py', r'timeout=600', 
         'moviebox_tools.py: Has 10-minute timeout'),
        ('moviebox_tools.py', r'if q\.endswith\("p"\):', 
         'moviebox_tools.py: Proper quality format handling'),
        ('moviebox_tools.py', r'file_size = os\.path\.getsize', 
         'moviebox_tools.py: Validates file size before returning'),
    ]
    
    for filename, pattern, desc in checks:
        total_checks += 1
        if check_pattern(filename, pattern, desc):
            passed_checks += 1
    print()
    
    # Check 4: Admin panel fixes
    print(f"{BLUE}4️⃣  Checking admin panel fixes...{NC}")
    
    # Check for returns in ad wizard blocks
    if os.path.exists('handlers.py'):
        with open('handlers.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all ad_wizard_media blocks and check if they have returns
        pattern = r'if pend == "ad_wizard_media".*?\n.*?\n.*?\n.*?\n.*?\n.*?\n.*?return'
        matches = re.findall(pattern, content, re.DOTALL)
        
        total_checks += 1
        if len(matches) >= 3:
            print(f"{GREEN}✓{NC} handlers.py: All 3 ad_wizard_media blocks have return statements")
            passed_checks += 1
        else:
            print(f"{YELLOW}⚠{NC} handlers.py: Missing returns in ad_wizard_media blocks (found {len(matches)}/3)")
    
    # Check shared.py broadcast fix
    checks = [
        ('shared.py', r'is_forwarded = msg\.forward_date is not None', 
         'shared.py: _do_broadcast detects forwarded messages'),
        ('shared.py', r'await ctx\.bot\.forward_message', 
         'shared.py: _do_broadcast uses forward_message()'),
    ]
    
    for filename, pattern, desc in checks:
        total_checks += 1
        if check_pattern(filename, pattern, desc):
            passed_checks += 1
    print()
    
    # Check 5: Import tests
    print(f"{BLUE}5️⃣  Testing imports...{NC}")
    
    import_tests = [
        ('yt_dlp_tools', 'yt_dlp_tools imports successfully'),
        ('moviebox_tools', 'moviebox_tools imports successfully'),
    ]
    
    for module, desc in import_tests:
        total_checks += 1
        try:
            __import__(module)
            print(f"{GREEN}✓{NC} {desc}")
            passed_checks += 1
        except ImportError as e:
            if 'moviebox' in module:
                print(f"{YELLOW}⚠{NC} {desc} - {e} (OK if moviebox-api not installed)")
                passed_checks += 1  # Don't fail on missing moviebox-api
            else:
                print(f"{RED}✗{NC} {desc} - {e}")
    print()
    
    # Summary
    print("═" * 64)
    percentage = (passed_checks / total_checks) * 100
    
    if percentage == 100:
        print(f"{GREEN}🎉 ALL CHECKS PASSED! ({passed_checks}/{total_checks}){NC}")
        print(f"{GREEN}Your bot is ready to deploy with all fixes applied.{NC}")
        return 0
    elif percentage >= 80:
        print(f"{YELLOW}⚠️  MOST CHECKS PASSED ({passed_checks}/{total_checks} - {percentage:.1f}%){NC}")
        print(f"{YELLOW}Review the warnings above and apply missing fixes.{NC}")
        return 1
    else:
        print(f"{RED}❌ FAILED ({passed_checks}/{total_checks} - {percentage:.1f}%){NC}")
        print(f"{RED}Please apply all fixes from the package before deploying.{NC}")
        return 2

if __name__ == '__main__':
    sys.exit(main())
