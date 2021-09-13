#!/usr/bin/env python3

import os
import re
import sys
import math
sys.dont_write_bytecode = True

REAL_FILE = os.path.abspath(__file__)
REAL_NAME = os.path.basename(REAL_FILE)
REAL_PATH = os.path.dirname(REAL_FILE)
if os.path.islink(__file__):
    LINK_FILE = REAL_FILE; REAL_FILE = os.path.abspath(os.readlink(__file__))
    LINK_NAME = REAL_NAME; REAL_NAME = os.path.basename(REAL_FILE)
    LINK_PATH = REAL_PATH; REAL_PATH = os.path.dirname(REAL_FILE)

DIR = os.path.abspath(os.path.dirname(REAL_FILE))
CWD = os.path.abspath(os.getcwd())
REL = os.path.relpath(DIR, CWD)

NAME, EXT = os.path.splitext(REAL_NAME)

from ruamel import yaml
from itertools import chain, product
from leatherman.dbg import dbg
from leatherman.repr import __repr__
from leatherman.yaml import yaml_format, yaml_print
from argparse import ArgumentParser, RawDescriptionHelpFormatter, Action


class PercentageError(Exception):
    def __init__(self, value):
        msg = f'Percentage Error: value={value}'
        super().__init__(msg)

class DivisionsPerConferenceError(Exception):
    def __init__(self, division_count, conference_count):
        msg = f'Divisions Per Conference Error: division_count={division_count}, conference_count={conference_count}'
        super().__init__(msg)

class TeamsPerConferenceError(Exception):
    def __init__(self, team_count, conference_count):
        msg = f'Teams Per Conference Error: team_count={team_count}, conference_count={conference_count}'
        super().__init__(msg)

class TeamsPerDivisionError(Exception):
    def __init__(self, team_count, division_count):
        msg = f'Teams Per Division Error: team_count={team_count}, division_count={division_count}'
        super().__init__(msg)

def list_sub(list1, list2):
    return [
        item
        for item
        in list1
        if item not in list2
    ]

def matchup_fmt(away, home):
    return f'{away} @ {home}'

def sort_home_away(matchups):
    i = 0
    while i < len(matchups):
        matchup_reversed = tuple(reversed(matchups[i]))
        matchups.remove(matchup_reversed)
        matchups.insert(i+1, matchup_reversed)
        i += 2
    return matchups

def percentage(num, msg='num should be 0-100'):
    if num < 0:
        raise PercentageError
    elif num == 0:
        return 0.0
    elif num <= 100:
        return num / 100

def divides_evenly(num, den):
    return num % den == 0

class Scheduler:
    def __init__(
        self,
        conference_count,
        division_count,
        team_count,
        week_count,
        nights_per_week,
        games_per_night,
        own_div_series_home_away,
        other_div_series_home_away,
        league=None,
        **kwargs):

        self.conference_count = conference_count
        self.division_count = division_count
        self.team_count = team_count
        self.week_count = week_count
        self.nights_per_week = nights_per_week
        self.games_per_night = games_per_night
        self.own_div_series_home_away = own_div_series_home_away
        self.other_div_series_home_away = other_div_series_home_away
        self.league = league or self.create_league()
        self.matchups = []
        self.schedule = {}

    __repr__ = __repr__

    @property
    def total_matchups(self):
        return self.total_games * int(self.team_count / 2)

    @property
    def conferences(self):
        return list(self.league.keys())

    @property
    def divisions(self):
        return list(chain(*[
            divs.keys()
            for conf, divs
            in self.league.items()
        ]))

    @property
    def teams(self):
        return list(chain(*[
            chain(*divs.values())
            for conf, divs
            in self.league.items()
        ]))
    @property
    def total_games(self):
        return self.week_count * self.nights_per_week * self.games_per_night

    @property
    def total_games_own_conf(self):
        return self.total_games_own_div + self.total_games_other_div

    @property
    def pct_games_own_conf(self):
        return int(self.total_games_own_conf / self.total_games * 100)

    @property
    def total_games_other_conf(self):
        return self.total_games - self.total_games_own_conf

    @property
    def pct_games_other_conf(self):
        return int(self.total_games_other_conf / self.total_games * 100)

    @property
    def total_games_own_conf(self):
        return self.total_games_own_div + self.total_games_other_div

    @property
    def pct_games_own_conf(self):
        return int(self.total_games_own_conf / self.total_games * 100)

    @property
    def total_games_own_div(self):
        return self.matchups_own_div_home_away * self.own_div_series_home_away

    @property
    def pct_games_own_div(self):
        return int(self.total_games_own_div / self.total_games * 100)

    @property
    def total_games_other_div(self):
        return (self.divs_per_conf - 1) * self.matchups_other_div_home_away * self.other_div_series_home_away

    @property
    def pct_games_other_div(self):
        return int(self.total_games_other_div / self.total_games * 100)

    @property
    def divs_per_conf(self):
        if divides_evenly(self.division_count, self.conference_count):
            return int(self.division_count / self.conference_count)
        raise DivisionsPerConferenceError(self.division_count, self.conference_count)

    @property
    def teams_per_conf(self):
        if divides_evenly(self.team_count, self.conference_count):
            return int(self.team_count / self.conference_count)
        raise TeamsPerConferenceError(self.team_count, self.conference_count)

    @property
    def teams_per_div(self):
        if divides_evenly(self.team_count, self.division_count):
            return int(self.team_count / self.division_count)
        raise TeamsPerDivisionError(self.team_count, self.division_count)

    @property
    def matchups_own_div(self):
        return self.teams_per_div - 1

    @property
    def matchups_other_div(self):
        return self.teams_per_div

    @property
    def matchups_own_div_home_away(self):
        return self.matchups_own_div * 2

    @property
    def matchups_other_div_home_away(self):
        return self.teams_per_div * 2

    @property
    def matchups_other_conf_home_away(self):
        return self.teams_per_conf * 2

    def get_conf_from_div(self, div):
        return int(div / self.divs_per_conf)

    def get_own_conf_teams(self, conf):
        conf = self.conferences[conf]
        return list(chain(*[
            teams
            for div, teams
            in self.league[conf].items()
        ]))

    def get_other_confs_teams(self, div):
        conf = self.get_conf_from_div(div)
        confs = [c for c in range(self.conference_count) if c != conf]
        return list(chain(*[
            self.get_own_conf_teams(conf)
            for conf
            in confs
        ]))

    def get_own_div_teams(self, div):
        if div < 0:
            div += self.division_count
        conf = self.get_conf_from_div(div)
        conf = self.conferences[conf]
        div = self.divisions[div]
        return self.league[conf][div]

    def get_other_divs_teams(self, div):
        if div < 0:
            div += self.divistion_count
        conf = self.get_conf_from_div(div)
        conf_teams = self.get_own_conf_teams(conf)
        div_teams = self.get_own_div_teams(div)
        return list_sub(conf_teams, div_teams)

    def matchup_filter(self, team):
        return [
            matchup
            for matchup
            in self.matchups
            if team in matchup
        ]

    def print_stats(self):
        print(f'total-games: {self.total_games}')
        print(f'total_matchups: {self.total_matchups}')
        print(f'div-per-conf: {self.divs_per_conf}')
        print(f'teams-per-div: {self.teams_per_div}')
        print(f'matchups-own-div: {self.matchups_own_div}')
        print(f'matchups-other-div: {self.matchups_other_div}')
        print(f'matchups-own-div-home-away: {self.matchups_own_div_home_away}')
        print(f'matchups-other-div-home-away: {self.matchups_other_div_home_away}')
        print(f'matchups-other-conf-home-away: {self.matchups_other_conf_home_away}')
        print(f'own-div-series-home-away: {self.own_div_series_home_away}')
        print(f'other-div-series-home-away: {self.other_div_series_home_away}')
        print(f'total-games-own-conf: {self.total_games_own_conf}/{self.total_games} ({self.pct_games_own_conf}%)')
        print(f'total-games-other-conf: {self.total_games_other_conf}/{self.total_games} ({self.pct_games_other_conf}%)')
        print(f'total-games-own-div: {self.total_games_own_div}/{self.total_games} ({self.pct_games_own_div}%)')
        print(f'total-games-other-div: {self.total_games_other_div}/{self.total_games} ({self.pct_games_other_div}%)')

    def create_league(self):
        league = {}
        for c in range(self.conference_count):
           letter = chr(c+65)
           conf = f'Conf{letter}'
           league[conf] = {}
           div_offset = c * self.divs_per_conf + 1
           for d in range(self.divs_per_conf):
               div = f'Div{div_offset+d}'
               league[conf][div] = []
               team_offset = c * self.teams_per_conf + d * self.teams_per_div + 1
               for t in range(self.teams_per_div):
                   team = f'Team{team_offset+t}'
                   league[conf][div] += [team]
        return league

    def create_own_div_matchups(self):
        matchups = []
        for conf, divs in self.league.items():
            for div, teams in divs.items():
                matchups += [
                    matchup
                    for matchup
                    in product(teams, teams)
                    if matchup[0] != matchup[1]
                ]
        return sort_home_away(matchups) * self.own_div_series_home_away

    def create_other_div_matchups(self):
        matchups = []
        for d in range(self.division_count):
            own_teams = self.get_own_div_teams(d)
            other_teams = self.get_other_divs_teams(d)
            matchups += product(own_teams, other_teams)
        return sort_home_away(matchups) * self.other_div_series_home_away

    def create_other_conf_matchups(self, home_away):
        decimal, integer = math.modf(home_away); integer = int(integer)
        matchups = []
        for d in range(self.division_count):
            own_teams = self.get_own_div_teams(d)
            other_conf_teams = self.get_other_confs_teams(d)
            matchups += product(own_teams, other_conf_teams)
        matchups = sort_home_away(matchups)
        matchups *= integer
        leftover_home_away_count = int(self.matchups_other_conf_home_away * decimal / 2)
        counter = {
            team: 0
            for team
            in self.teams
        }
        for away, home in matchups:
            if counter[away] < leftover_home_away_count and counter[home] < leftover_home_away_count:
                matchups += [
                    (away, home),
                    (home, away),
                ]
                counter[away] += 1
                counter[home] += 1
        return matchups

    def create_matchups(self):
        own_div = self.create_own_div_matchups()
        other_div = self.create_other_div_matchups()

        home_away = self.total_games_other_conf / self.matchups_other_conf_home_away
        other_conf = self.create_other_conf_matchups(home_away)
        matchups = len(own_div) + len(other_div) + len(other_conf)
        dbg(matchups)

    def create_week(self):
        pass

    def create_night(self):
        pass

    def create_game(self, game):
        return {
            f'Game{game}': [
                'A @ B',
            ] * self.team_count / 2
        }

    def create_schedule(self):
        self.schedule = {
            f'Week{w+1}': {
                f'Night{n+1}': {
                    f'Game{g+1}' : []
                    for g
                    in range(self.games_per_night)
                }
                for n
                in range(self.nights_per_week)
            }
            for w
            in range(self.week_count)
        }

def main(args=None):
    parser = ArgumentParser(
        description=__doc__,
        formatter_class=RawDescriptionHelpFormatter,
        add_help=False)
    parser.add_argument(
        '-c', '--config',
        metavar='FILEPATH',
        default='%(REL)s/%(NAME)s.yml' % globals(),
        help='default="%(default)s"; config filepath')
    ns, rem = parser.parse_known_args(args)
    try:
        config = {
            key.replace('-', '_'): value
            for key, value
            in yaml.safe_load(open(ns.config)).items()
        }
    except FileNotFoundError as er:
        config = dict()
    #finally:
    #    config = resolve(config)
    parser = ArgumentParser(
        parents=[parser])
    parser.set_defaults(**config)
    parser.add_argument(
        '--conference-count',
        metavar='INT',
        type=int,
        help='default="%(default)s"; conference count')
    parser.add_argument(
        '--division-count',
        metavar='INT',
        type=int,
        help='default="%(default)s"; division count')
    parser.add_argument(
        '--team-count',
        metavar='INT',
        type=int,
        help='default="%(default)s"; division count')
    parser.add_argument(
        '--week-count',
        metavar='INT',
        type=int,
        help='default="%(default)s"; weeks count')
    parser.add_argument(
        '--nights-per-week',
        metavar='INT',
        type=int,
        help='default="%(default)s"; nights count')
    parser.add_argument(
        '--games-per-night',
        metavar='INT',
        type=int,
        help='default="%(default)s"; games count')
    parser.add_argument(
        '--own-div-series-home-away',
        metavar='INT',
        type=int,
        help='default="%(default)s"; own div home|away count')
    parser.add_argument(
        '--other-div-series-home-away',
        metavar='INT',
        type=int,
        help='default="%(default)s"; other div home|away count')
    ns = parser.parse_args(rem)
    s = Scheduler(**ns.__dict__)
    s.create_matchups()
    s.create_schedule()
    s.print_stats()

if __name__ == '__main__':
    main(sys.argv[1:])

