{
  description = "agent-kit: install Cursor, Claude Code, and ~/.agents links from a checkout";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs =
    { nixpkgs, ... }:
    let
      # nixpkgs-unstable dropped x86_64-darwin.
      systems = [
        "aarch64-darwin"
        "aarch64-linux"
        "x86_64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };

      # Always run against a working checkout. Linking ~/.cursor and ~/.claude
      # into the nix store would make config read-only and GC-fragile.
      mkInstallApp =
        pkgs: action:
        let
          name =
            {
              install = "agent-kit-install";
              uninstall = "agent-kit-uninstall";
              status = "agent-kit-status";
            }
            .${action};
          extraArgs =
            {
              install = "";
              uninstall = " --uninstall";
              status = " --status";
            }
            .${action};
        in
        {
          type = "app";
          program = "${
            pkgs.writeShellApplication {
              inherit name;
              runtimeInputs = [ pkgs.python3 ];
              text = ''
                repo="''${AGENT_KIT_REPO:-}"
                if [[ -z "$repo" && -f "''${PWD}/scripts/install.py" && -f "''${PWD}/manifest.json" ]]; then
                  repo="$PWD"
                fi
                if [[ -z "$repo" ]]; then
                  echo "agent-kit: run from a checkout of this repo, or set AGENT_KIT_REPO" >&2
                  echo "Example: git clone <this-repo> ~/Code/agent-kit && cd ~/Code/agent-kit && nix run .#${action}" >&2
                  exit 1
                fi
                exec python3 "$repo/scripts/install.py" --repo "$repo"${extraArgs} "$@"
              '';
            }
          }/bin/${name}";
          meta.description =
            {
              install = "Link this checkout into ~/.cursor, ~/.claude, and ~/.agents";
              uninstall = "Remove this repo's links from host directories";
              status = "Show whether host directories point at this checkout";
            }
            .${action};
        };
    in
    {
      apps = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = mkInstallApp pkgs "install";
          install = mkInstallApp pkgs "install";
          uninstall = mkInstallApp pkgs "uninstall";
          status = mkInstallApp pkgs "status";
        }
      );

      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
        in
        {
          default = pkgs.mkShell {
            packages = [
              pkgs.python3
              pkgs.git
            ];
            shellHook = ''
              echo "agent-kit shell"
              echo "  nix run .#install    # link this checkout to ~/.cursor ~/.claude ~/.agents"
              echo "  nix run .#status"
              echo "  python3 scripts/install.py --status"
            '';
          };
        }
      );

      formatter = forAllSystems (system: (pkgsFor system).nixfmt);

      # Import from home-manager. repo must be a checkout path string, not a
      # Nix path (those copy into the store).
      homeModules.default =
        {
          config,
          lib,
          pkgs,
          ...
        }:
        let
          cfg = config.programs.agent-kit;
        in
        {
          options.programs.agent-kit = {
            enable = lib.mkEnableOption "agent-kit checkout linked into Cursor, Claude Code, and ~/.agents";
            repo = lib.mkOption {
              type = lib.types.str;
              default =
                "${config.home.homeDirectory}/"
                + (if pkgs.stdenv.hostPlatform.isDarwin then "Code/agent-kit" else "code/agent-kit");
              defaultText = lib.literalExpression ''
                if pkgs.stdenv.hostPlatform.isDarwin
                then "''${config.home.homeDirectory}/Code/agent-kit"
                else "''${config.home.homeDirectory}/code/agent-kit"
              '';
              description = ''
                Working checkout of this repo. Defaults to ~/Code/agent-kit on
                Darwin and ~/code/agent-kit on Linux/WSL. Must be a string, not a
                Nix path — those copy into the store.
              '';
            };
            remote = lib.mkOption {
              type = lib.types.str;
              default = "https://github.com/sknutsen/agent-kit.git";
              description = "Git URL cloned when repo does not exist. Existing checkouts are left alone.";
            };
          };

          config = lib.mkIf cfg.enable {
            home.activation.agentKit = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
              repo="${cfg.repo}"
              repo="''${repo/#\~/${config.home.homeDirectory}}"
              if [[ ! -e "$repo" ]]; then
                echo "agent-kit: cloning ${cfg.remote} -> $repo"
                run mkdir -p "$(dirname "$repo")"
                run ${lib.getExe pkgs.git} clone ${lib.escapeShellArg cfg.remote} "$repo"
              elif [[ ! -f "$repo/scripts/install.py" ]]; then
                echo "agent-kit: $repo exists but is not this checkout; skipping"
              fi
              if [[ -f "$repo/scripts/install.py" ]]; then
                run ${lib.getExe pkgs.python3} "$repo/scripts/install.py" --repo "$repo"
              fi
            '';
          };
        };
    };
}
