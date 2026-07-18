"""Creates (or updates, idempotently) the svc-netbox-mcp service account.

This account is a fallback only: real MCP usage authenticates as the
calling user's own NetBox token (pass-through, see
`netbox_mcp.auth.get_current_token`), not as this shared account. It exists
for integration tests, CI, and local dev where no per-user token is wired
up yet.

Permissions granted (tracks `client/registry.py`'s current object coverage,
not a permanent limit — widen this script's app list as the registry grows
toward full NetBox coverage):
- DCIM + IPAM: view/add/change/delete. `delete` is included because the
  client only ever calls delete() inside an active `netbox_branching`
  branch (see `client/rest.py::NetBoxRestClient.delete`) — nothing this
  account deletes can reach `main` without a human merge, so the
  object-level delete permission itself is not the safety boundary.
- netbox_branching: view_branch + add_branch only, so this account can
  create the branches it writes into and check their status.

Deliberately NOT granted, on this or any account the MCP server uses:
merge_branch, sync_branch, revert_branch, archive_branch. Those apply (or
discard) a branch's changes against `main` and are meant to stay a human
action taken from the NetBox UI after reviewing the branch's diff — this is
the actual approval gate, not the DCIM/IPAM delete permission above.

Usage (from a running NetBox Docker stack):

    docker compose --env-file env/version.conf -p netbox-docker exec -T netbox \\
        python manage.py shell < /path/to/netbox-mcp/scripts/create_service_account.py

Prints the plaintext API token at the end: copy it into NETBOX_API_TOKEN
(local .env, not committed).

The account and the permissions are idempotent (get_or_create). The token
is NOT: NetBox 4.6 creates "v2" tokens by default (hashed — the plaintext
is never stored and is only retrievable once, at creation time). To stay
compatible with netbox-mcp's REST client (Authorization: Token <value>,
classic v1 scheme), this script explicitly forces version=1 and deletes any
existing token for the account before creating a new one — otherwise the
plaintext would be irrecoverably lost as soon as an old token already
exists in the database. Re-running this script therefore revokes the
previous token and issues a new one.
"""

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from users.choices import TokenVersionChoices
from users.models import ObjectPermission, Token

USERNAME = "svc-netbox-mcp"

DCIM_IPAM_PERMISSION_NAME = "svc-netbox-mcp-dcim-ipam"
DCIM_IPAM_APPS = ["dcim", "ipam"]
DCIM_IPAM_ACTIONS = ["view", "add", "change", "delete"]

BRANCHING_PERMISSION_NAME = "svc-netbox-mcp-branching"
BRANCHING_ACTIONS = ["view", "add"]  # never merge/sync/revert/archive

User = get_user_model()

user, user_created = User.objects.get_or_create(
    username=USERNAME,
    defaults={"is_active": True},
)
if user_created:
    user.set_unusable_password()
    user.save()
    print(f"[OK] user '{USERNAME}' created")
else:
    print(f"[OK] user '{USERNAME}' already exists (id={user.id})")

dcim_ipam_content_types = ContentType.objects.filter(app_label__in=DCIM_IPAM_APPS)

dcim_ipam_permission, dcim_ipam_created = ObjectPermission.objects.get_or_create(
    name=DCIM_IPAM_PERMISSION_NAME,
    defaults={"actions": DCIM_IPAM_ACTIONS, "enabled": True},
)
dcim_ipam_permission.actions = DCIM_IPAM_ACTIONS
dcim_ipam_permission.enabled = True
dcim_ipam_permission.save()
dcim_ipam_permission.object_types.set(dcim_ipam_content_types)
dcim_ipam_permission.users.set([user])

verb = "created" if dcim_ipam_created else "updated"
print(
    f"[OK] permission '{DCIM_IPAM_PERMISSION_NAME}' {verb}: "
    f"{dcim_ipam_content_types.count()} content types ({', '.join(DCIM_IPAM_APPS)}), "
    f"actions {DCIM_IPAM_ACTIONS}"
)

branch_content_type = ContentType.objects.get(
    app_label="netbox_branching", model="branch"
)

branching_permission, branching_created = ObjectPermission.objects.get_or_create(
    name=BRANCHING_PERMISSION_NAME,
    defaults={"actions": BRANCHING_ACTIONS, "enabled": True},
)
branching_permission.actions = BRANCHING_ACTIONS
branching_permission.enabled = True
branching_permission.save()
branching_permission.object_types.set([branch_content_type])
branching_permission.users.set([user])

verb = "created" if branching_created else "updated"
print(
    f"[OK] permission '{BRANCHING_PERMISSION_NAME}' {verb}: "
    f"actions {BRANCHING_ACTIONS} (merge/sync/revert/archive intentionally excluded)"
)

stale_count, _ = Token.objects.filter(user=user).delete()
if stale_count:
    print(f"[OK] {stale_count} stale token(s) deleted")

token = Token(
    user=user,
    description="netbox-mcp service account",
    version=TokenVersionChoices.V1,
)
token.save()
print("[OK] new v1 token created")
print("TOKEN_START")
print(token.token)
print("TOKEN_END")
