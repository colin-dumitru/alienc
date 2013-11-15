#!/usr/bin/python3

import os
import json
import urllib.request
import time
import curses
import curses.ascii
import sys
import textwrap
import html.parser 

class State:
	running = True

	screen = None
	commandScreen = None
	pageQueue = []
	rows = 0
	columns = 0

	command = ""
	commandArgs = []

	headers = { 'User-Agent' : 'reddit reader by /u/-colin-' }

	preferred = [
		'all', 'linux', 'ubuntu', 'europe', 'romania', 'technology', 'programming', 'worldnews', 'games', 'formula1', 'bicycling'
	]

	def setDimensions (dimensions):
		State.rows = int(dimensions[0])
		State.columns = int(dimensions[1])

class Article:
	def __init__ (self, json):
		self.title = json['data']['title']
		self.score = json['data']['score']
		self.permalink = json['data']['permalink']
		self.body = json['data'].get('selftext', "None")

class Comment:
	def __init__(self, json):
		self.body = json['data']['body']
		self.ups = json['data']['ups']
		self.downs = json['data']['downs']
		self.author = json['data']['author']

		if not json['data']['replies']:
			self.children = []
			return

		self.children = [
			Comment(obj)
			for obj in json['data']['replies']['data']['children']
			if obj['kind'] == 't1'
		]

class SubredditPage:
	def __init__(self, subreddit):
		self.subreddit = subreddit
		self.order = 'hot'
		self.articles = []
		self.lineIndex = 0
		self.selectedArticle = 0

	def render(self, reload = True):	

		if reload:
			self.lineIndex = 0
			self.selectedArticle = 0

			self.loadArticles()
		self.renderArticles()	
		self.renderSubreddit()

		State.screen.refresh()

	def renderArticles(self):
		State.screen.clear()
		line = self.lineIndex
		maxLines = self.lineIndex + State.rows
		
		while (line < len(self.articles) and line < maxLines):
			article = self.articles[line]
			text = "[%s] %s" % (str(article.score).rjust(4), article.title)

			if(self.selectedArticle == line):
				State.screen.addstr(line - self.lineIndex, 0, text[:State.columns - 1], curses.A_STANDOUT)
			else:
				State.screen.addstr(line - self.lineIndex, 0, text[:State.columns - 1])

			line += 1

	def renderSubreddit(self):
		State.screen.addstr(State.rows - 1, 0, ("  %s" % self.subreddit).ljust(State.columns - 1), curses.A_STANDOUT)
	
	def loadArticles(self):	

		obj = json.loads(
			urllib.request.urlopen(
				urllib.request.Request("http://www.reddit.com/r/%s/%s.json" % (self.subreddit, self.order), None, State.headers)
			).read().decode('utf-8')
		)

		self.articles = [
			Article(child)
			for child in obj['data']['children']
		]

	def moveUp(self):
		self.selectedArticle = max(self.selectedArticle - 1, 0)
		self.lineIndex = min(self.lineIndex, self.selectedArticle)
		self.renderArticles()

	def moveDown(self):
		self.selectedArticle = min(self.selectedArticle + 1, len(self.articles) - 1)
		self.lineIndex = max(self.lineIndex, self.selectedArticle - State.rows + 1)
		self.renderArticles()

	def showTop(self):
		self.order = 'top'
		self.render()

	def showHot(self):
		self.order = 'hot'
		self.render()

	def showNew(self):
		self.order = 'new'
		self.render()

	def changeSubreddit(self):
		self.subreddit = State.commandArgs[0]
		self.render()

	def showComments(self):
		State.pageQueue.append(CommentPage(self.articles[self.selectedArticle]))
		refresh()

	def nextSubreddit(self):
		index = (State.preferred.index(self.subreddit) + 1) % len(State.preferred)
		self.subreddit = State.preferred[index]
		self.render()

	def prevSubreddit(self):
		index = (State.preferred.index(self.subreddit) - 1) % len(State.preferred)
		self.subreddit = State.preferred[index]
		self.render()

	def longCommand(self):
		def doNothing():
			pass		

		{
			'r': self.changeSubreddit
		}.get(State.command, doNothing)()

	def command(self, keyCode):
		def doNothing():
			pass	
		{
			0: self.longCommand,

			338: self.nextSubreddit, #PAGE DOWN
			339: self.prevSubreddit, #PAGE UP

			curses.KEY_UP: self.moveUp,
			curses.KEY_DOWN: self.moveDown,
			curses.KEY_RIGHT: self.showComments,

			ord('t') : self.showTop,
			ord('n') : self.showNew,
			ord('h') : self.showHot
		}.get(keyCode, doNothing)()


class CommentPage:
	def __init__(self, article):
		self.article = article
		self.comments = []
		self.order = 'top'
		
	def render(self, reload = True):
		self.buildRenderer()
		self.renderer.render()
		State.screen.refresh()

		self.loadComments()

	def buildRenderer(self):
		text = "%s\n%s\n%s" % (
			self.article.title,
			''.join(['-' for i in range (0, State.columns - 1)]),
			self.article.body
		)
		
		self.renderer = StringPage(text)

	def showRootComments(self):
		page = SingleCommentPage(self.comments)
		State.pageQueue.append(page)
		refresh()

	def loadComments(self):
		obj = json.loads(
			urllib.request.urlopen(
				urllib.request.Request("http://www.reddit.com%s.json?sort=%s" % (self.article.permalink[:-1], self.order), None, State.headers)
			).read().decode('utf-8')
		)

		self.comments = [
			Comment(comment)
			for rootNode in obj
			for comment in rootNode['data']['children']
			if comment['kind'] == 't1'
		]

	def showTop(self):
		self.order = 'top'
		self.render()

	def showNew(self):
		self.order = 'new'
		self.render()

	def showHot(self):
		self.order = 'hot'
		self.render()

	def command(self, keyCode):
		def doNothing():
			pass	

		{
			338: self.renderer.scrollDown, #PAGE DOWN
			339: self.renderer.scrollUp, #PAGE UP

			curses.KEY_RIGHT: self.showRootComments,

			ord('t') : self.showTop,
			ord('n') : self.showNew,
			ord('h') : self.showHot
		}.get(keyCode, doNothing)()
		pass

class SingleCommentPage:
	def __init__(self, comments, level = 1):
		self.comments = comments
		self.level = level
		self.selectedComment = 0
		
	def render(self, reload = True):
		self.buildRenderer()
		self.renderer.render()
		State.screen.refresh()

	def buildRenderer(self):
		if(not self.comments):
			text = 'No comments'
		else:
			text = "[%d/%d] %s\n%s\n\n%s" % (
				self.comments[self.selectedComment].ups,
				self.comments[self.selectedComment].downs,
				self.comments[self.selectedComment].author,
				''.join(['#' for i in range(0, min(State.rows, self.level))]),
				self.comments[self.selectedComment].body
			)
		
		self.renderer = StringPage(text)

	def nextComment(self):
		self.selectedComment = min(self.selectedComment + 1, len(self.comments) - 1)
		self.buildRenderer()
		self.renderer.render()
		State.screen.refresh()

	def previousComment(self):
		self.selectedComment = max(self.selectedComment - 1, 0)
		self.buildRenderer()
		self.renderer.render()
		State.screen.refresh()

	def showChildComments(self):
		if(not self.comments):
			return

		page = SingleCommentPage(self.comments[self.selectedComment].children, self.level + 1)
		State.pageQueue.append(page)
		refresh()

	def command(self, keyCode):
		def doNothing():
			pass	

		{
			338: self.renderer.scrollDown, #PAGE DOWN
			339: self.renderer.scrollUp, #PAGE UP

			curses.KEY_UP: self.previousComment,
			curses.KEY_DOWN: self.nextComment,
			curses.KEY_RIGHT: self.showChildComments,

			#ord('t') : self.showTop,
			#ord('n') : self.showNew,
			#ord('h') : self.showHot
		}.get(keyCode, doNothing)()
		pass

class StringPage:
	def __init__(self, text):
		self.text = str(text.encode('utf-8').decode('ascii', 'ignore'))
		self.lines = []
		self.lineIndex = 0

		self.processText()

	def processText(self):
		self.lines = [
			line
			for paragraph in self.text.split('\n')
			for line in textwrap.wrap(paragraph, State.columns - 1)
		]

	def scrollUp(self):
		self.lineIndex = max(self.lineIndex - 1, 0)
		self.render()

	def scrollDown(self):
		self.lineIndex = min(self.lineIndex + 1, max(len(self.lines) - State.rows, 0))
		self.render()

	def render(self, reload = True):
		State.screen.clear()
		lineIndex = 0

		for line in self.lines[self.lineIndex: self.lineIndex + State.rows]:
			State.screen.addstr(lineIndex, 0, line)
			lineIndex += 1
			

def refresh():
	State.pageQueue[-1:][0].render(False)

def reload():
	State.pageQueue[-1:][0].render(True)

def init():
	os.environ['PYTHONIOENCODING='] = 'utf_8'
	State.screen = curses.initscr()

	curses.noecho()
	curses.cbreak()
	State.screen.keypad(True)
	State.setDimensions(State.screen.getmaxyx())

	State.commandScreen = curses.newwin(1, State.columns, State.rows - 1, 0)

def quit():
	curses.nocbreak()
	State.screen.keypad(False)
	curses.echo()
	curses.endwin()

	State.running = False

def processCommand(keyCode):
	def delegate():
		State.pageQueue[-1].command(keyCode)

	def goBack():
		if len(State.pageQueue) > 1:
			State.pageQueue.pop()
			refresh()

	{
		ord('r'): reload,
		ord('q'): quit,
		curses.KEY_LEFT: goBack
	}.get(keyCode, delegate)()

def readCommand(keyCode, readingCommand):
	if not readingCommand:
		State.command = ""
		State.commandArgs = []

	if keyCode == 10: #enter key
		commandArgs = State.command.split(" ")
		State.command = commandArgs[0][1:] #remove : character
		State.commandArgs = commandArgs[1:]
		return False
	elif keyCode == 27: #escape key
		State.command = ""
		State.commandArgs = []
		return False
	else:
		State.command += chr(keyCode) 
		State.commandScreen.addstr(0, 0, State.command[:State.columns - 1])
		State.commandScreen.refresh()
		return True


def main():
	init()
	
	State.pageQueue.append(SubredditPage('all'))
	reload()

	readingCommand = False

	while State.running:
		key = State.screen.getch()

		if readingCommand or key == ord(':'):
			readingCommand = readCommand(key, readingCommand)

			if not readingCommand:
				processCommand(0)
		else:
			processCommand(key)

		time.sleep(0.01)

if __name__ == '__main__':
	main()