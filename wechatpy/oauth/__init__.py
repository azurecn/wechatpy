# -*- coding: utf-8 -*-
"""
    wechatpy.oauth
    ~~~~~~~~~~~~~~~

    This module provides OAuth2 library for WeChat

    :copyright: (c) 2014 by messense.
    :license: MIT, see LICENSE for more details.
"""
from __future__ import absolute_import, unicode_literals

import requests
from six.moves.urllib.parse import quote

from wechatpy.utils import json
from wechatpy.exceptions import WeChatOAuthException


class WeChatOAuth(object):
    """微信公众平台 OAuth 网页授权 """

    _http = requests.Session()

    API_BASE_URL = 'https://api.weixin.qq.com/'
    OAUTH_BASE_URL = 'https://open.weixin.qq.com/connect/'

    def __init__(self, app_id, secret, redirect_uri,
                 scope='snsapi_base', state='', js_code=False):
        """

        :param app_id: 微信公众号 app_id
        :param secret: 微信公众号 secret
        :param redirect_uri: OAuth2 redirect URI
        :param scope: 可选，微信公众号 OAuth2 scope，默认为 ``snsapi_base``
        :param state: 可选，微信公众号 OAuth2 state
        :param js_code: 小程序授权时请传入True
        """
        self.app_id = app_id
        self.secret = secret
        self.redirect_uri = redirect_uri
        self.scope = scope
        self.state = state
        self.js_code = js_code

    def _request(self, method, url_or_endpoint, **kwargs):
        if not url_or_endpoint.startswith(('http://', 'https://')):
            url = '{base}{endpoint}'.format(
                base=self.API_BASE_URL,
                endpoint=url_or_endpoint
            )
        else:
            url = url_or_endpoint

        if isinstance(kwargs.get('data', ''), dict):
            body = json.dumps(kwargs['data'], ensure_ascii=False)
            body = body.encode('utf-8')
            kwargs['data'] = body

        res = self._http.request(
            method=method,
            url=url,
            **kwargs
        )
        try:
            res.raise_for_status()
        except requests.RequestException as reqe:
            raise WeChatOAuthException(
                errcode=None,
                errmsg=None,
                client=self,
                request=reqe.request,
                response=reqe.response
            )
        result = json.loads(res.content.decode('utf-8', 'ignore'), strict=False)

        if 'errcode' in result and result['errcode'] != 0:
            errcode = result['errcode']
            errmsg = result['errmsg']
            raise WeChatOAuthException(
                errcode,
                errmsg,
                client=self,
                request=res.request,
                response=res
            )

        return result

    def _get(self, url, **kwargs):
        return self._request(
            method='get',
            url_or_endpoint=url,
            **kwargs
        )

    @property
    def authorize_url(self):
        """获取授权跳转地址

        :return: URL 地址
        """
        redirect_uri = quote(self.redirect_uri, safe='')
        url_list = [
            self.OAUTH_BASE_URL,
            'oauth2/authorize?appid=',
            self.app_id,
            '&redirect_uri=',
            redirect_uri,
            '&response_type=code&scope=',
            self.scope
        ]
        if self.state:
            url_list.extend(['&state=', self.state])
        url_list.append('#wechat_redirect')
        return ''.join(url_list)

    @property
    def qrconnect_url(self):
        """生成扫码登录地址

        :return: URL 地址
        """
        redirect_uri = quote(self.redirect_uri, safe='')
        url_list = [
            self.OAUTH_BASE_URL,
            'qrconnect?appid=',
            self.app_id,
            '&redirect_uri=',
            redirect_uri,
            '&response_type=code&scope=',
            'snsapi_login'  # scope
        ]
        if self.state:
            url_list.extend(['&state=', self.state])
        url_list.append('#wechat_redirect')
        return ''.join(url_list)

    def fetch_access_token(self, code):
        """获取 access_token

        :param code: 授权完成跳转回来后 URL 中的 code 参数
        :return: JSON 数据包
        """
        params = dict(
            appid=self.app_id,
            secret=self.secret,
            grant_type='authorization_code'
        )
        if self.js_code:
            oauth2_url = 'sns/jscode2session'       # 小程序请求路由
            params['js_code'] = code
        else:
            oauth2_url = 'sns/oauth2/access_token'  # 普通公众号请求路由
            params['code'] = code
        res = self._get(
            oauth2_url,
            params=params
        )
        self.access_token = res['access_token']
        self.open_id = res['openid']
        self.refresh_token = res['refresh_token']
        self.expires_in = res['expires_in']
        return res

    def refresh_access_token(self, refresh_token):
        """刷新 access token

        :param refresh_token: OAuth2 refresh token
        :return: JSON 数据包
        """
        res = self._get(
            'sns/oauth2/refresh_token',
            params={
                'appid': self.app_id,
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token
            }
        )
        self.access_token = res['access_token']
        self.open_id = res['openid']
        self.refresh_token = res['refresh_token']
        self.expires_in = res['expires_in']
        return res

    def get_user_info(self, openid=None, access_token=None, lang='zh_CN'):
        """获取用户信息

        :param openid: 可选，微信 openid，默认获取当前授权用户信息
        :param access_token: 可选，access_token，默认使用当前授权用户的 access_token
        :param lang: 可选，语言偏好, 默认为 ``zh_CN``
        :return: JSON 数据包
        """
        openid = openid or self.open_id
        access_token = access_token or self.access_token
        return self._get(
            'sns/userinfo',
            params={
                'access_token': access_token,
                'openid': openid,
                'lang': lang
            }
        )

    def check_access_token(self, openid=None, access_token=None):
        """检查 access_token 有效性

        :param openid: 可选，微信 openid，默认获取当前授权用户信息
        :param access_token: 可选，access_token，默认使用当前授权用户的 access_token
        :return: 有效返回 True，否则 False
        """
        openid = openid or self.open_id
        access_token = access_token or self.access_token
        res = self._get(
            'sns/auth',
            params={
                'access_token': access_token,
                'openid': openid
            }
        )
        if res['errcode'] == 0:
            return True
        return False
