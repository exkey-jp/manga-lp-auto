"""Chatwork に知らせる（CHATWORK_TOKEN と CHATWORK_ROOM_ID が設定されているときだけ）。"""
import requests

from . import config as C


def notify(job, text):
    url = f'{C.APP_BASE_URL}/jobs/{job.id}'
    body = f'[info][title]漫画LP：{job.name}[/title]{text}\n{url}[/info]'
    job.log('通知：' + text)
    if not (C.CHATWORK_TOKEN and C.CHATWORK_ROOM_ID):
        return
    try:
        requests.post(f'https://api.chatwork.com/v2/rooms/{C.CHATWORK_ROOM_ID}/messages',
                      headers={'X-ChatWorkToken': C.CHATWORK_TOKEN}, data={'body': body}, timeout=20)
    except Exception as e:
        job.log(f'Chatwork への通知に失敗：{e}')
