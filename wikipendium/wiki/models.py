from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import datetime
from wikipendium.wiki.langcodes import LANGUAGE_NAMES
from markdown import Markdown
from .markdown_extra.markdown_wikitables import WikiTableExtension


class Article(models.Model):
    slug = models.SlugField(max_length=256, unique=True)

    @staticmethod
    def get_all_article_content():
        articles = Article.objects.all()

        all_newest_in_all_languages = [
            [a.get_newest_content(lang)
                for lang in a.get_available_language_codes()]
            for a in articles]

        return all_newest_in_all_languages

    @staticmethod
    def get_all_newest_contents():
        all_newest_in_all_languages = Article.get_all_article_content()

        all_newest_reduced_to_one_ac_per_article_regardless_of_language = map(
            lambda x: sorted(x, key=lambda ac: ac.updated)[0],
            filter(lambda x: x, all_newest_in_all_languages))

        alphabetically_sorted = sorted(
            all_newest_reduced_to_one_ac_per_article_regardless_of_language,
            key=lambda ac: ac.article.slug)
        return alphabetically_sorted

    @staticmethod
    def get_all_newest_contents_all_languages():
        all_newest_in_all_languages = Article.get_all_article_content()

        flattened_list = [article
                          for sublist in all_newest_in_all_languages
                          for article in sublist]
        alphabetically_sorted = sorted(flattened_list,
                                       key=lambda ac: ac.article.slug)

        return alphabetically_sorted

    def __unicode__(self):
        return self.slug

    def save(self):
        self.slug = self.slug.upper().strip()
        self.clean()
        super(Article, self).save()

    def clean(self):
        if '/' in self.slug:
            raise ValidationError('Course code cannot contain slashes')

    def get_contributors(self, lang='en'):
        filtered = ArticleContent.objects.filter(article=self, lang=lang)
        return set([ac.edited_by for ac in filtered])

    def get_newest_content(self, lang='en'):
        try:
            filtered = ArticleContent.objects.filter(article=self, lang=lang)
            return filtered.order_by('-updated')[:1].get()
        except:
            return None

    def get_sorted_contents(self, lang='en'):
        filtered = ArticleContent.objects.filter(article=self, lang=lang)
        return filtered.order_by('-updated')

    def get_available_language_codes(self):
        codes = ArticleContent.objects.filter(
            article=self
        ).distinct().values_list('lang', flat=True)
        return list(codes)

    def get_available_languages(self, current=None):
        codes = self.get_available_language_codes()
        if current and current.lang is not None and current.lang in codes:
            codes.remove(current.lang)
        if codes:
            return zip(map(lambda key: LANGUAGE_NAMES[key], codes),
                       map(self.get_newest_content, codes))

    def get_absolute_url(self, lang="en"):
        newest_content = self.get_newest_content(lang)
        if newest_content is not None:
            return newest_content.get_absolute_url()
        return "/" + self.slug + "/" + lang + "/edit/"

    def get_slug(self):
        return self.slug.upper()


class ArticleContent(models.Model):
    article = models.ForeignKey('Article')
    content = models.TextField()
    title = models.CharField(max_length=1024)
    lang = models.CharField(max_length=2, default='en')
    updated = models.DateTimeField()
    edited_by = models.ForeignKey(User, blank=True,
                                  null=True, on_delete=models.SET_NULL)
    parent = models.ForeignKey('ArticleContent', related_name='parent_ac',
                               null=True, blank=True,
                               on_delete=models.SET_NULL)
    child = models.ForeignKey('ArticleContent', related_name='child_ac',
                              null=True, blank=True, on_delete=models.SET_NULL)

    def clean(self):
        if '/' in self.title:
            raise ValidationError('Title cannot contain slashes')

    def get_contributors(self):
        filtered = ArticleContent.objects.filter(article=self.article,
                                                 lang=self.lang,
                                                 updated__lt=self.updated)
        return set([ac.edited_by for ac in filtered]) | set([self.edited_by])

    def get_full_title(self):
        return self.article.slug + ': ' + self.title

    def get_absolute_url(self):
        lang = ""
        if self.lang != "en":
            lang = '/' + self.lang + '/'
        return '/' + self.article.slug + "_" + \
               self.title.replace(' ', '_') + lang

    def get_edit_url(self):
        return (self.get_absolute_url() + '/edit/').replace('//', '/')

    def get_add_language_url(self):
        return "/" + self.article.slug + "/add_language/"

    def get_history_url(self):
        return (self.get_absolute_url() + '/history/').replace('//', '/')

    def get_history_single_url(self):
        return self.get_history_url() + str(self.pk)+'/'

    def get_html_content(self):
        wikitables = WikiTableExtension()

        md = Markdown(
            extensions=[
                'toc',
                'outline',
                'mathjax',
                wikitables,
            ],
            output_format='html5',
            safe_mode='escape'
        )
        markdowned_text = md.convert(self.content)
        article = {
            'html': markdowned_text,
            'toc': md.toc,
        }
        return article

    def save(self, change_updated_time=True):
        if change_updated_time:
            self.updated = datetime.datetime.now()
        super(ArticleContent, self).save()

    def __unicode__(self):
        return '[' + str(self.pk) + '] ' + self.title
