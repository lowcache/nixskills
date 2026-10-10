# Secrets (sops-nix)

## Rule zero
Nothing secret ever enters the Nix store (world-readable). No secret in Nix strings, `environment.etc.*.text`, `builtins.readFile`, or derivation args. Consume via file paths at runtime: `config.sops.secrets.<n>.path`, `*File`/`environmentFile`/`passwordFile` options, or `sops.templates`.

## Setup
- `.sops.yaml` `creation_rules` map paths → age recipients. Host recipient from SSH host key: `ssh-to-age < /etc/ssh/ssh_host_ed25519_key.pub` (on impermanence, the persisted key).
- `sops.defaultSopsFile = ./secrets/secrets.yaml;`
- `sops.age.sshKeyPaths = [ "/persist/etc/ssh/ssh_host_ed25519_key" ];` **or** `sops.age.keyFile` — must point at a path that exists at early activation (persisted, not a bind mount that's set up later).

## Per secret
```nix
sops.secrets."tailscale/authkey" = {
  owner = "root"; mode = "0400";
  restartUnits = [ "tailscaled.service" ];   # rotate → service restarts
};
```
- `neededForUsers = true` for user password hashes (`users.users.<u>.hashedPasswordFile`).
- Config files mixing secrets and plain text: `sops.templates."app.env".content = "TOKEN=${config.sops.placeholder.token}";` → use `config.sops.templates."app.env".path`.
- Home-manager has its own `sops` module (decrypts to `$XDG_RUNTIME_DIR`); requires a user age key.

## Operations
- Edit: `sops secrets/secrets.yaml`. New recipient/host: add to `.sops.yaml`, then `sops updatekeys secrets/secrets.yaml`.
- Rotation: change value, rebuild; `restartUnits` handles consumers.

## Debug
- `journalctl -b -u sops-nix` (or activation output): "no key could decrypt" → wrong/missing key path or recipient not in file (`updatekeys`).
- Secret path exists but service can't read it → `owner`/`mode`, or `DynamicUser` service (use `LoadCredential=` instead).
- Grep the closure for leaks before switching: `nix path-info -r ./result | xargs grep -l "<distinctive secret prefix>" 2>/dev/null`.
