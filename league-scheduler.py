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

from random import seed, randint
from ruamel import yaml
from copy import deepcopy
from addict import Addict
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

def league_fmt(obj):
    if isinstance(obj, dict):
        return {
            key: league_fmt(value)
            for key, value
            in obj.items()
        }
    if isinstance(obj, list):
        return [
            league_fmt(item)
            for item
            in obj
        ]
    if isinstance(obj, tuple):
        away, home = obj
        return f'{away} @ {home}'
    if isinstance(obj, str):
        return obj
    raise Exception(f'type(obj)={type(obj)}')

def league_print(obj, title=None):
    output = deepcopy({title: obj} if title else obj)
    yaml_print(league_fmt(output))

class Scheduler:
    def __init__(
        self,
        random_seed,
        conference_count,
        division_count,
        team_count,
        week_count,
        nights_per_week,
        games_per_night,
        own_div_series_home_away,
        other_div_series_home_away,
        nights,
        games,
        league=None,
        **kwargs):

        self.random_seed = random_seed
        self.conference_count = conference_count
        self.division_count = division_count
        self.team_count = team_count
        self.week_count = week_count
        self.nights_per_week = nights_per_week
        self.games_per_night = games_per_night
        self.own_div_series_home_away = own_div_series_home_away
        self.other_div_series_home_away = other_div_series_home_away
        self.nights = nights
        self.games = games
        self.league = league or self.create_league()
        self.matchups = []
        self.schedule = Addict()

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
        return self.bundle_matchups(matchups * self.own_div_series_home_away)

    def create_other_div_matchups(self):
        matchups = []
        for d in range(self.division_count):
            own_teams = self.get_own_div_teams(d)
            other_teams = self.get_other_divs_teams(d)
            matchups += product(own_teams, other_teams)
        return self.bundle_matchups(matchups * self.other_div_series_home_away)

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
        return self.bundle_matchups(matchups)

    def bundle_matchups(self, matchups):
        '''
        bundle list of matchups into list of lists bundles for game times
        '''
        count = len(matchups) // (len(self.teams) // 2)
        results = []
        for i in range(count):
            results += [[]]
            teams = deepcopy(self.teams)
            j = 0
            while teams:
                away, home = matchups[j]
                if away in teams and home in teams:
                    teams = list(set(teams) - set([away, home]))
                    results[i] += [(away, home)]
                    matchups.pop(j)
                else:
                    j += 1
        return results

    def create_schedule(self):
        home_away = self.total_games_other_conf / self.matchups_other_conf_home_away
        other_conf = self.create_other_conf_matchups(home_away)
        other_div = self.create_other_div_matchups()
        own_div = self.create_own_div_matchups()

        self.create_own_div_opening_week_schedule(own_div, other_div)
        self.create_other_2nd_week_schedule(other_div, other_conf)
        self.create_other_conf_cup_preview_schedule(other_conf)
        self.create_last_2wks_div_push_schedule(own_div, other_div)
        self.create_random_middle_schedule(own_div, other_div, other_conf)
        league_print(self.schedule)

    def build_time_slot(self, week, night, game, label, matchups):
        '''
        week, night and game are expected to be zero-based; therefore +1 to each to be one-based
        '''
        self.schedule[f'Week{week+1}'][f'Night{night+1} ({self.nights[night]})'][f'Game{game+1} ({self.games[game]})'] = {
            'label': label,
            'matchups': matchups,
        }

    def create_own_div_opening_week_schedule(self, own_div, other_div):
        for n in range(self.nights_per_week):
            for g in range(self.games_per_night):
                if g % 2:
                    self.build_time_slot(0, n, g, 'Opening Week Conference Matchups', other_div.pop(0))
                else:
                    self.build_time_slot(0, n, g, 'Opening Week Divisional Matchups', own_div.pop(0))

    def create_other_2nd_week_schedule(self, other_div, other_conf):
        for n in range(self.nights_per_week):
            for g in range(self.games_per_night):
                if g % 2:
                    self.build_time_slot(1, n, g, 'Second Week Extra-conference Matchups', other_conf.pop(0))
                else:
                    self.build_time_slot(1, n, g, 'Second Week Conference Matchups', other_div.pop(0))

    def create_random_middle_schedule(self, own_div, other_div, other_conf):
        if self.random_seed:
            seed(self.random_seed)
        for w in range(2, 5):
            for n in range(self.nights_per_week):
                for g in range(self.games_per_night):
                    matchups = None
                    while matchups is None:
                        matchups_list = (
                            own_div,
                            other_div,
                            other_conf
                        )
                        labels = (
                            'Heart of the Schedule Divisional Matchups',
                            'Heart of the Schedule Conference Matchups',
                            'Heart of the Schedule Extra-conference Matchups',
                        )
                        r = randint(0, len(matchups_list)-1)
                        if len(matchups_list[r]):
                            label = labels[r]
                            matchups = matchups_list[r].pop(0)
                    self.build_time_slot(w, n, g, label, matchups)

    def create_other_conf_cup_preview_schedule(self, other_conf):
        third_to_last_week = self.week_count - 3
        for n in range(self.nights_per_week):
            for g in range(self.games_per_night):
                self.build_time_slot(third_to_last_week, n, g, 'Extra-conference Cup Preview Matchups', other_conf.pop(0))

    def create_last_2wks_div_push_schedule(self, own_div, other_div):
        for w in range(self.week_count - 2, self.week_count):
            for n in range(self.nights_per_week):
                for g in range(self.games_per_night):
                    if g % 2:
                        self.build_time_slot(w, n, g, 'Playoffs Push Conference Matchups', other_div.pop(0))
                    else:
                        self.build_time_slot(w, n, g, 'Playoffs Push Divisional Matchups', own_div.pop(0))

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
    parser = ArgumentParser(
        parents=[parser])
    parser.set_defaults(**config)
    parser.add_argument(
        '--random-seed',
        metavar='INT',
        type=int,
        help='default="%(default)s"; set random seed')
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
    s.create_schedule()
    s.print_stats()

if __name__ == '__main__':
    main(sys.argv[1:])

