{ config, pkgs, lib, ... }:
let
  cfg = config.services.live-dynamic;

  btDynamic = pkgs.python3Packages.buildPythonPackage rec {
    pname = "bt_dynamic";
    version = "0.1.3";
    pyproject = true;
    src = pkgs.python3Packages.fetchPypi {
      inherit pname version;
      hash = "sha256-NVuvUkr0BpedpaYIjXdeOQH62EeQewX2+AWk9XE5d0M=";
    };
    build-system = [ pkgs.python3Packages.hatchling ];
    dependencies = with pkgs.python3Packages; [ pandas numpy ];
  };

  pyEnv = pkgs.python3.withPackages (ps: with ps; [ pandas numpy btDynamic ]);

  commonEnvironment = [
    "PYTHONPATH=${cfg.appRoot}"
    "LIVE_DYNAMIC_DATA=${cfg.dataRoot}"
    "MARKET_DATA=${cfg.marketDataRoot}"
    "BT_DYNAMIC_CONFIG=${cfg.dataRoot}/env/config.json"
  ];

  mkOneshot = name: script: enabled: lib.mkIf enabled {
    description = "live-dynamic ${name}";
    after = [ "network-online.target" ];
    wantedBy = [ "default.target" ];
    serviceConfig = {
      Type = "oneshot";
      Environment = commonEnvironment;
      ExecStart = "${pyEnv}/bin/python3 ${cfg.appRoot}/core/${script}";
    };
  };

  mkTimer = name: onCalendar: enabled: lib.mkIf enabled {
    description = "live-dynamic ${name} timer";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnCalendar = onCalendar;
      AccuracySec = "1s";
      Persistent = true;
    };
  };
in
{
  options.services.live-dynamic = {
    enable = lib.mkEnableOption "live-dynamic trading system";
    orchestrator = lib.mkEnableOption "signal + send pipeline timer";
    haltCheck = lib.mkEnableOption "kill-switch check timer";
    eodClose = lib.mkEnableOption "end-of-day close timer";
    tokenRefresh = lib.mkEnableOption "token refresh timer";
    fetchBars = lib.mkEnableOption "bar fetch timer";

    user = lib.mkOption {
      type = lib.types.str;
      description = "User the timers run as (systemd user units).";
    };
    appRoot = lib.mkOption {
      type = lib.types.str;
      description = "Checkout of this repository.";
    };
    dataRoot = lib.mkOption {
      type = lib.types.str;
      description = "LIVE_DYNAMIC_DATA directory (state / logs / env).";
    };
    marketDataRoot = lib.mkOption {
      type = lib.types.str;
      description = "MARKET_DATA directory (bars / tokens).";
    };

    sessionEndHourUtc = lib.mkOption {
      type = lib.types.int;
      default = 17;
      description = "UTC hour of the EOD forced close; keep in sync with trade_end_hour in the strategy config.";
    };
  };

  config = lib.mkIf cfg.enable {
    systemd.user.tmpfiles.rules = [
      "d ${cfg.dataRoot}/state 0755 ${cfg.user} users -"
      "d ${cfg.dataRoot}/env 0755 ${cfg.user} users -"
      "d ${cfg.dataRoot}/logs 0755 ${cfg.user} users -"
      "d ${cfg.marketDataRoot}/state/tokens 0755 ${cfg.user} users -"
      "d ${cfg.marketDataRoot}/bars 0755 ${cfg.user} users -"
    ];

    systemd.user.services = {
      live-dynamic-orchestrator = mkOneshot "orchestrator" "orchestrator.py" cfg.orchestrator;
      live-dynamic-halt-check = mkOneshot "halt check" "halt_check.py" cfg.haltCheck;
      live-dynamic-eod-close = mkOneshot "EOD close" "eod_close.py" cfg.eodClose;
      live-dynamic-token-refresh = lib.mkIf cfg.tokenRefresh {
        description = "live-dynamic token refresh";
        after = [ "network-online.target" ];
        wantedBy = [ "default.target" ];
        serviceConfig = {
          Type = "oneshot";
          Environment = commonEnvironment;
          ExecStart = "${pyEnv}/bin/python3 ${cfg.appRoot}/core/token_refresh.py";
          TimeoutStartSec = "20";
        };
      };
      live-dynamic-fetch-bars = mkOneshot "fetch bars" "fetch_bars.py" cfg.fetchBars;
    };

    systemd.user.timers = {
      # decision pipeline: every 30 minutes during the session (Mon-Fri)
      live-dynamic-orchestrator = mkTimer "orchestrator"
        "Mon..Fri 00..${toString (cfg.sessionEndHourUtc - 1)}:5/30:00 UTC" cfg.orchestrator;
      # kill switch and data/token freshness: every 5 minutes
      live-dynamic-halt-check = mkTimer "halt check" "Mon..Fri *:0/5:00 UTC" cfg.haltCheck;
      live-dynamic-eod-close = mkTimer "EOD close"
        "Mon..Fri ${toString cfg.sessionEndHourUtc}:00:00 UTC" cfg.eodClose;
      live-dynamic-token-refresh = mkTimer "token refresh" "*:0/5:00 UTC" cfg.tokenRefresh;
      live-dynamic-fetch-bars = mkTimer "fetch bars" "*:0/5:00 UTC" cfg.fetchBars;
    };
  };
}
