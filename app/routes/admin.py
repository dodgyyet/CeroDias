"""Admin routes for resetting and managing game state"""
from flask import Blueprint, render_template, render_template_string, request, redirect, url_for, jsonify
from app.storage.memory_store import MemoryStore

bp = Blueprint('admin', __name__)
store = MemoryStore()

ADMIN_PASSWORD = 'admin'  # TODO: Change in production
CHAIN_COMPLETE_TOKEN = 'cerodias-admin-9f2a4c1b7e3d8a5f'

CHAIN_COMPLETE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CeroDias Security Assessment - Chain Complete</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background-color: #0a0a0a;
            color: #00ff41;
            font-family: 'Courier New', Courier, monospace;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .terminal {
            max-width: 700px;
            width: 100%;
            border: 1px solid #00ff41;
            padding: 2rem;
            background: #0d0d0d;
        }
        .terminal-header {
            border-bottom: 1px solid #005514;
            padding-bottom: 1rem;
            margin-bottom: 1.5rem;
        }
        h1 {
            font-size: 1rem;
            font-weight: normal;
            color: #00ff41;
            margin-bottom: 0.5rem;
        }
        .subtitle {
            color: #007a20;
            font-size: 0.85rem;
        }
        .status-line {
            margin: 1rem 0;
            font-size: 0.9rem;
        }
        .label { color: #007a20; }
        .value { color: #00ff41; }
        .value.verified { color: #00ff41; font-weight: bold; }
        .divider {
            border: none;
            border-top: 1px solid #005514;
            margin: 1.5rem 0;
        }
        .note {
            color: #005514;
            font-size: 0.8rem;
            line-height: 1.6;
        }
        .note span { color: #007a20; }
        .prompt { color: #005514; }
    </style>
</head>
<body>
    <div class="terminal">
        <div class="terminal-header">
            <h1>CeroDias Security Assessment</h1>
            <div class="subtitle">Internal verification system - restricted access</div>
        </div>

        <div class="status-line">
            <span class="label">Status         : </span>
            <span class="value verified">CHAIN COMPLETE</span>
        </div>
        <div class="status-line">
            <span class="label">Access level   : </span>
            <span class="value">root (uid=0)</span>
        </div>
        <div class="status-line">
            <span class="label">System         : </span>
            <span class="value">cerodias-prod-01</span>
        </div>
        <div class="status-line">
            <span class="label">Token verified : </span>
            <span class="value">{{ token }}</span>
        </div>

        <hr class="divider">

        <div class="status-line">
            You have compromised the CeroDias production system. Full root access confirmed.
        </div>

        <hr class="divider">

        <div class="note">
            <span>You are the attacker k.chen wrote about.</span><br><br>
            This token was extracted from <span>/root/.cerodias/admin_token</span> and
            confirms full attack chain completion: prompt injection, server-side template
            injection, SQL injection, PHP upload bypass, SSH key decryption, and privilege
            escalation to root.<br><br>
            The CeroDias monitoring platform and all customer alert data are accessible.
        </div>

        <hr class="divider">

        <div class="note">
            <span class="prompt">root@cerodias-prod-01:~#</span> <span>_</span>
        </div>
    </div>
</body>
</html>"""


@bp.route('/admin')
def admin_panel():
    """Admin panel"""
    return render_template('admin.html')


@bp.route('/admin/reset', methods=['POST'])
def reset_game():
    """Reset all game data"""
    password = request.form.get('password', '')

    if password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': 'Invalid password'}), 401

    store.reset()
    return jsonify({'success': True, 'message': 'Game reset successfully'})


@bp.route('/admin/chain-complete')
def chain_complete():
    """Chain completion verification endpoint"""
    token = request.args.get('token', '')
    if token != CHAIN_COMPLETE_TOKEN:
        return jsonify({'error': 'invalid token'}), 403
    return render_template_string(CHAIN_COMPLETE_PAGE, token=token)


@bp.route('/admin/stats')
def admin_stats():
    """Get admin statistics"""
    return jsonify({
        'total_players': len(store.players),
        'total_challenges': len(store.challenges),
        'leaderboard_entries': len(store.leaderboard),
    })
