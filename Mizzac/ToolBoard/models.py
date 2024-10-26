# ToolBoard/models.py

from django.db import models

class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.name

class Tool(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, default='default-slug')
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='tools')
    related_tools = models.ManyToManyField('self', blank=True, symmetrical=False)
    template_name = models.CharField(max_length=100, default='pages/tool_detail.html')

    class Meta:
        verbose_name = "Outil"
        verbose_name_plural = "Outils"

    def __str__(self):
        return self.name
