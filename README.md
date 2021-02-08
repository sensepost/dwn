<h1 align="center">
  <br>
    🥽 dwn
  <br>
  <br>
</h1>

<h4 align="center">d(ockerp)wn - a docker attack tool manager</h4>
<p align="center">
  <a href="https://twitter.com/leonjza"><img src="https://img.shields.io/badge/twitter-%40leonjza-blue.svg" alt="@leonjza" height="18"></a>
  <a href="https://pypi.python.org/pypi/dwn"><img src="https://badge.fury.io/py/dwn.svg" alt="PyPI version" height="18"></a>
</p>
<br>

## introduction

`dwn` is a "docker-compose for hackers". Using a simple YAML "plan" format similar to `docker-compose`, image names, versions and volume / port mappings are defined to setup a tool for use.

## features

With `dwn` you can:

- Configure common pentest tools for use in a docker container
- Have context aware volume mounts
- Dynamically modify port bindings without container restarts
- And more!

## installation

Simply run `pip3 install dwn`.

## usage

`dwn` is actually really simple. The primary concept is that of "plans" where information about a tool (such as name, version, mounts and binds) are defined. There are a few [built-in plans](plans/) already available, but you can also roll your own. Without arguments, just running `dwn` would look like this.

```text
❯ dwn
Usage: dwn [OPTIONS] COMMAND [ARGS]...

       __
   ___/ /    _____
  / _  / |/|/ / _ \
  \_,_/|__,__/_//_/
    docker pwn tool manager
    by @leonjza / @sensepost

Options:
  --debug  enable debug logging
  --help   Show this message and exit.

Commands:
  check    Check plans and Docker environment
  network  Work with networks
  plans    Work with plans
  run      Run a plan
  show     Show running plans
  stop     Stop a plan
```

To list the available plans, run `dwn plans show`.

```text
❯ dwn plans show
                                    dwn plans
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ name             ┃ path                                  ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ sqlmap           │ /tools/dwn/plans/sqlmap.yml           │
│ wpscan           │ /tools/dwn/plans/wpscan.yml           │
│ gowitness-report │ /tools/dwn/plans/gowitness-report.yml │
│ msfconsole       │ /tools/dwn/plans/msfconsole.yml       │
│ gowitness        │ /tools/dwn/plans/gowitness.yml        │
│ nginx            │ /tools/dwn/plans/nginx.yml            │
│ cme              │ /tools/dwn/plans/cme.yml              │
│ netcat-reverse   │ /tools/dwn/plans/netcat-reverse.yml   │
│ semgrep-sec      │ /tools/dwn/plans/semgrep-sec.yml      │
│ semgrep-ci       │ ~/.dwn/plans/semgrep-ci.yml           │
│ neo4j            │ ~/.dwn/plans/neo4j.yml                │
└──────────────────┴───────────────────────────────────────┘
                                     11 plans
```

To run a plan such as `gowitness` screenshotting <https://google.com>, run `dwn run gowitness --disable-db single https://www.google.com`. This plan will exit when done, so you don’t have to `dwn stop gowitness`.

```text
❯ dwn run gowitness --disable-db single https://www.google.com
(i) found plan for gowitness
(i) volume: ~/scratch -> /data
(i) streaming container logs
08 Feb 2021 10:46:18 INF preflight result statuscode=200 title=Google url=https://www.google.com
❯
❯ ls screenshots
https-www.google.com.png
```

A plan such as `netcat-reverse` however will stay alive. You can connect to the plans TTY after it is started to interact with any shells you may receive. Example usage would be:

```text
❯ dwn run netcat-reverse
(i) found plan for netcat-reverse
(i) port: 4444<-4444
(i) container booted! attach & detach commands are:
(i) attach: docker attach dwn_wghz_netcat-reverse
(i) detach: ctrl + p, ctrl + q
```

Attaching to the plan (and executing `nc -e` somewhere else)

```text
❯ docker attach dwn_wghz_netcat-reverse
connect to [::ffff:172.19.0.2]:4444 from dwn_wghz_netcat-reverse_net_4444_4444.dwn:46318 ([::ffff:172.19.0.3]:46318)

env | grep -i shell
SHELL=/bin/zsh

read escape sequence
```

You can get a running plan report too

```text
❯ dwn show
                                running plan report
┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ plan           ┃ container(s)                          ┃ port(s)    ┃ volume(s) ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ netcat-reverse │ dwn_wghz_netcat-reverse_net_4444_4444 │ 4444<-4444 │           │
│                │ dwn_wghz_netcat-reverse               │            │           │
└────────────────┴───────────────────────────────────────┴────────────┴───────────┘
```

And finally, stop a plan.

```text
❯ dwn stop netcat-reverse -y
(i) stopping 2 containers for plan netcat-reverse
```

## networking

`dwn` lets you dynamically map ports to plans without any container restarts. Networking commands live under the `dwn network` subcommand. Taking the [nginx](plans/nginx.yml) plan as an example, we can add a port mapping dynamically. First, start the `nginx` plan.

```text
❯ dwn run nginx
(i) found plan for nginx
(i) volume: ~/scratch -> /usr/share/nginx/html
(i) port: 80<-8888
(i) container dwn_wghz_nginx started for plan nginx, detaching
```

Next, test the communication with cURL

```text
❯ curl localhost:8888/poo.txt
haha, you touched it!

❯ curl localhost:9000/poo.txt
curl: (7) Failed to connect to localhost port 9000: Connection refused
```

Port 9000 is not open, so let's add a new port binding and test connectivity

```text
❯ dwn network add nginx -i 80 -o 9000
(i) port binding for 9000->nginx:80 created
❯
❯ curl localhost:9000/poo.txt
haha, you touched it!
```

## updating plans

The `dwn plans pull` command can be used to update the `images` defined in plans. To only update a single plan, add the plan name after `pull`. Eg: `dwn plans pull nginx`.

## writing plans

A `dwn plans new` command exists to quickly scaffold a new plan. While only a few options are needed to get a plan up and running, all of the options that exist in the Python Docker SDK for the [run](https://docker-py.readthedocs.io/en/stable/containers.html#docker.models.containers.ContainerCollection.run) call are valid tags that can be used.

## license

`dwn` is licensed under a [GNU General Public v3 License](https://www.gnu.org/licenses/gpl-3.0.en.html). Permissions beyond the scope of this license may be available at <http://sensepost.com/contact/>.
