import datetime
import numpy
import pickle
import requests
import time

## This class is used to build the data structures contained in
# /data folder. There is no need to rebuild them this file is
# just included to show how those structures were built.

class DataBuilder():
    """Fetches/builds data required for app."""
    def __init__(self) -> None:
        pass

    def _getStats(self, api: str, timeout:int=None) -> dict:
        """Helper method to make API requests.

        Args:
            api (str): endpoint of the API call.
            timeout (_type_, optional): Seconds to wait for a response. Defaults to None.

        Returns:
            dict: JSON response from the server.
        """
        return requests.get(f"https://statsapi.web.nhl.com/api/v1/{api}", timeout=timeout).json()
    
    def _gamesPlayed(self, win_matrix: numpy.ndarray) -> numpy.ndarray:
        """Calculated the total number of games played against an opponent for
        every team in <win_matrix>.

        Args:
            win_matrix (numpy.ndarray): A team x team dimension win matrix.

        Returns:
            numpy.ndarray: A team x team dimension matrix whose entries indicate
            how many times the row team played the column team.
        """
        return numpy.sum(win_matrix, axis=0, dtype=float) + numpy.sum(win_matrix, axis=1, dtype=float)
    
    def _getAllSeasons(self) -> list[str]:
        """Get a list of all NHL seasons from the API.

        Returns:
            list[str]: Every season in 'yyyyyyyy'
            format, e.g., '19251926'
        """
        seasons_data = self._getStats("seasons")
        seasons_list = []
        for season in seasons_data["seasons"]:
            seasons_list.append(season["seasonId"])
        return seasons_list

    def _readFile(self, name: str) -> object:
        """Helper to read pickled objects.

        Args:
            name (str): Name of the pickled object.

        Returns:
            object: Unpickled object.
        """
        with open(f"./data/{name}", "rb") as infile:
            file = pickle.load(infile)
            infile.close()
        return file
        
    def _writeFile(self, file: object, name: str) -> None:
        """Helper to pickle objects.

        Args:
            file (object): The object to pickle.
            name (str): The file name to write the pickled object to.
        """
        with open(f"./data/{name}", "wb") as outfile:
            pickle.dump(file, outfile)
            outfile.close()

    def _testEndpoint(self, id: int, dict: dict) -> tuple[int | None, None | str, None | int]:
        """Test the API for a given team id.

        Args:
            id (int): Id to test the API with.
            dict (dict): Team name to team id lookup.

        Returns:
            tuple[int | None, None | str, None | int]: 
            If the first element is not None it is <id> and indicates an error occured during the API call.
            The second element is the team name associated with <id>, None if an error occurs.
            The last element is the team id associated with <id>, None if an error occurs.
        """
        print(f"Scraping endpoint teams/{id}", end="\r")
        try:
            response = self._getStats(f"teams/{id}", timeout=1)
        except Exception as e:
            print(f"\nException {e} occured querying id {id}.")
            time.sleep(1)
            return id, None, None

        if "teams" in response:
            if "name" in response["teams"][0]:
                if response["teams"][0]["name"] not in dict:
                    name = response["teams"][0]["name"]
                    team_id = response["teams"][0]["id"]
            elif response["teams"][0]["locationName"] not in dict:
                name = response["teams"][0]["locationName"]
                team_id = response["teams"][0]["id"]
        else:
            name = None
            team_id = None

        time.sleep(1)
        return None, name, team_id

    def buildSeasonLookup(self) -> None:
        """Builds a season to SOS.csv column lookup dictionary."""
        try:
            seasons_list = self._readFile("seasons_list.pickle")
        except:
            seasons_list = self._getAllSeasons()
            self._writeFile(seasons_list, "seasons_list.pickle")

        seasons_lookup = {
            seasons_list[i][:4]+"-"+seasons_list[i][4:]: i for i in range(len(seasons_list))
        }

        self._writeFile(seasons_lookup, "seasons_lookup.pickle")

    def buildNameFromIdLookup(self) -> None:
        """Builds a team id to team name look up dictionary.
        WARNING: This function can take multiple hours to finish running!!
        """
        skipped_ids = []
        id_from_name = {}
        name_from_id = {}
        for id in range(10001):
            skipped_id, name, team_id = self._testEndpoint(id, id_from_name)
            if skipped_id is not None:
                skipped_ids.append(skipped_id)
            else:
                id_from_name[name] = team_id

        while len(skipped_ids) > 0:
            for id in skipped_ids.copy():
                skipped_id, name, team_id = self._testEndpoint(id, id_from_name)
                if skipped_id is None:
                    id_from_name[name] = team_id
                    skipped_ids.pop(skipped_ids.index(id))
        
        for name, id in id_from_name.items():
            name_from_id[id] = name

        self._writeFile(id_from_name, "id_from_name.pickle")
        self._writeFile(name_from_id, "name_from_id.pickle")

    def buildSOS(self) -> None:
        """Builds a csv of SOS statistics for every team in every season."""
        try:
            seasons_list = self._readFile("seasons_list.pickle")
        except:
            seasons_list = self._getAllSeasons()
            self._writeFile(seasons_list, "seasons_list.pickle")

        # A team x season sos matrix.
        nhl_sos = numpy.zeros((59, len(seasons_list)))

        for column_idx, season in enumerate(seasons_list):

            # Get data from the api.
            season_dates = self._getStats(f"seasons/{season}")["seasons"][0]
            division_records = self._getStats(f"standings?season={season}")["records"]
            season_data = self._getStats(f"schedule?season={season}")

            # Get the regular season start and end dates of <season>.
            start_date = season_dates["regularSeasonStartDate"]
            start_date = datetime.date.fromisoformat(start_date)
            end_date = season_dates["regularSeasonEndDate"]
            end_date = datetime.date.fromisoformat(end_date)

            # Build a team id -> win matrix row index lookup dictionary.
            win_matrix_row_from_id = {}
            row = 0
            for division in division_records:
                for team in division["teamRecords"]:
                    win_matrix_row_from_id[team["team"]["id"]] = row
                    row += 1

            # Build a win matrix row index to team id lookup dictionary.
            id_from_win_matrix_row = {}
            for id, wm_row in win_matrix_row_from_id.items():
                id_from_win_matrix_row[wm_row] = id

            # Make an empty win matrix.
            num_teams = len(win_matrix_row_from_id)
            win_matrix = numpy.zeros((num_teams, num_teams))

            # Populate the win matrix.
            for day in season_data["dates"]:
                date = datetime.date.fromisoformat(day["date"])
                if (start_date <= date) and (date <= end_date):
                    for game in day["games"]:
                        away_score = game["teams"]["away"]["score"]
                        home_score = game["teams"]["home"]["score"]
                        away_id = game["teams"]["away"]["team"]["id"]
                        home_id = game["teams"]["home"]["team"]["id"]
                        # Handle All-Star/Exhibition Games.
                        if home_id > 58 or away_id > 58:
                            continue

                        if away_score > home_score:
                            try:
                                win_matrix[win_matrix_row_from_id[away_id]][win_matrix_row_from_id[home_id]] += 1
                            except Exception as e:
                                print(f"Exception {e} occured handling game {game} in the {season} season.")
                        elif home_score > away_score:
                            try:
                                win_matrix[win_matrix_row_from_id[home_id]][win_matrix_row_from_id[away_id]] += 1
                            except Exception as e:
                                print(f"Exception {e} occured handling game {game} in the {season} season.")

            # Get a matrix of how many times a team played another.
            opp_plays = win_matrix + numpy.transpose(win_matrix)

            # Initialize an all 0 list to hold each teams OW%
            ow = [0] * len(win_matrix_row_from_id.keys())

            # Calculate the teams OW% from the win matrix.
            for team in win_matrix_row_from_id.values():
                sub_wins = numpy.copy(win_matrix)
                sub_wins[team] = 0
                sub_wins[:,team] = 0
                wins = numpy.sum(sub_wins, axis=1, dtype=float)
                games = self._gamesPlayed(sub_wins)
                oppWs = numpy.divide(wins, games, out=numpy.zeros_like(wins), where=games!=0)
                ow[team] = oppWs @ numpy.transpose(opp_plays[team]) / self._gamesPlayed(win_matrix)[team]

            # Calculate each teams OOW%.
            oow = opp_plays @ numpy.transpose(ow) / self._gamesPlayed(win_matrix)

            # Calculate each teams SoS.
            sos = (2*numpy.asarray(ow) + oow) / 3

            for idx, stat in enumerate(sos):
                nhl_sos[id_from_win_matrix_row[idx]][column_idx] = stat

        numpy.savetxt('data/sos.csv', nhl_sos, delimiter=',')

        return None
    
# data_builder = DataBuilder()

# data_builder.buildSeasonLookup()

# This should finish in ~20 seconds.
# data_builder.buildSOS()

# WARINING: This function is how the name/id lookups were build.
# It scrapes the API to find all teams and ids within 10000 endpoints.
# Running this can take MULTIPLE HOURS to test all endpoints.
# data_builder.buildNameFromIdLookup()