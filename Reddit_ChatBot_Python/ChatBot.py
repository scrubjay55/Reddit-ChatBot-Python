from .Utils.WebSockClient import WebSockClient
from .Utils.ChatMedia import ChatMedia
import requests
import pickle
import re
from .RedditAuthentication import TokenAuth, PasswordAuth


class ChatBot:
    _SB_ai = '2515BDA8-9D3A-47CF-9325-330BC37ADA13'
    REDDIT_OAUTH_HOST = "https://oauth.reddit.com"
    REDDIT_SENDBIRD_HOST = "https://s.reddit.com"

    def __init__(self, authentication, with_chat_media=False, store_session=True, **kwargs):
        assert isinstance(authentication, (TokenAuth, PasswordAuth)), "Wrong Authentication type"
        reddit_api_token = authentication.authenticate()

        self.headers = {'user-agent': "Reddit/Version 2020.41.1/Build 296539/Android 11", 'authorization': f'Bearer {reddit_api_token}'}

        if store_session:
            sb_access_token, user_id = self._load_session(reddit_api_token)
        else:
            sb_access_token, user_id = self._get_new_session()

        self.WebSocketClient = WebSockClient(key=sb_access_token, ai=self._SB_ai, user_id=user_id, **kwargs)
        if with_chat_media:  # this is untested
            self.ChatMedia = ChatMedia(key=sb_access_token, ai=self._SB_ai, reddit_api_token=reddit_api_token)

    @staticmethod
    def authenticate_with_password(username, password):
        headers = {'User-Agent': 'Firefox'}
        data = {
            'op': 'login',
            'user': username,
            'passwd': password
        }
        response = requests.post(f'{ChatBot.REDDIT_NORMAL}/post/login', headers=headers, data=data, allow_redirects=False)
        redditsession = response.cookies.get("reddit_session")
        chat_r = requests.get(f'{ChatBot.REDDIT_NORMAL}/chat/', headers=headers, cookies={"reddit_session": redditsession})
        sendbird_scoped_token = re.search(b'"accessToken":"(.*?)"', chat_r.content).group(1).decode()
        return sendbird_scoped_token

    def join_channel(self, sub, channel_url):
        if channel_url.startswith("sendbird_group_channel_"):
            channel_url_ = channel_url
        else:
            channel_url_ = "sendbird_group_channel_" + channel_url
        sub_id = self._get_sub_id(sub)
        data = f'{{"channel_url":"{channel_url_}","subreddit":"{sub_id}"}}'
        resp = requests.post(f'{ChatBot.REDDIT_SENDBIRD_HOST}/api/v1/sendbird/join', headers=self.headers, data=data)
        return resp.text

    def get_sendbird_channel_urls(self, sub_name):
        sub_id = self._get_sub_id(sub_name)
        response = requests.get(f'{ChatBot.REDDIT_SENDBIRD_HOST}/api/v1/subreddit/{sub_id}/channels', headers=self.headers)
        response.raise_for_status()
        try:
            rooms = response.json().get('rooms')
            for room in rooms:
                yield room.get('url')
        except (KeyError, IndexError):
            raise Exception('Sub doesnt have any rooms')

    def _load_session(self, pkl_name):
        try:
            session_store_f = open(f'{pkl_name}.pkl', 'rb')
            sb_access_token = pickle.load(session_store_f)
            user_id = pickle.load(session_store_f)
            print("loading from session goes brrr")
        except FileNotFoundError:
            session_store_f = open(f'{pkl_name}.pkl', 'wb+')
            sb_access_token, user_id = self._get_new_session()
            pickle.dump(sb_access_token, session_store_f)
            pickle.dump(user_id, session_store_f)
        finally:
            session_store_f.close()

        return sb_access_token, user_id

    def _get_new_session(self):
        sb_access_token = self._get_sendbird_access_token()
        user_id = self._get_user_id()

        return sb_access_token, user_id

    def _get_sendbird_access_token(self):
        response = requests.get(f'{ChatBot.REDDIT_SENDBIRD_HOST}/api/v1/sendbird/me', headers=self.headers)
        response.raise_for_status()
        return response.json()['sb_access_token']

    def _get_user_id(self):
        response = requests.get(f'{ChatBot.REDDIT_OAUTH_HOST}/api/v1/me.json', headers=self.headers)
        response.raise_for_status()
        return 't2_' + response.json().get('id')

    def _get_sub_id(self, sub_name):
        response = requests.get(f'{ChatBot.REDDIT_OAUTH_HOST}/r/{sub_name}/about.json', headers=self.headers)
        response.raise_for_status()
        sub_id = response.json().get('data').get('name')
        if sub_id is None:
            raise Exception('Wrong subreddit name')
        return sub_id
