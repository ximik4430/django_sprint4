from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)

from blog.forms import CommentForm, PostForm, ProfileForm
from blog.models import Category, Comment, Post


class ProfileLoginView(LoginView):
    def get_success_url(self):
        url = reverse(
            'blog:profile',
            args=(self.request.user.get_username(),)
        )
        return url


def edit_profile(request, name):
    '''Изменение профиля пользователя.'''
    user = get_object_or_404(User, username=name)
    if user.username != request.user.username:
        return redirect('login')
    form = ProfileForm(request.POST or None, instance=user)
    context = {'form': form}
    if form.is_valid():
        form.save()
    return render(request, 'blog/user.html', context)


def get_paginated_posts(posts, page_number):
    paginator = Paginator(posts, settings.POSTS_PAGE)
    page_obj = paginator.get_page(page_number)
    return page_obj


def info_profile(request, name):
    '''Информация о профиле пользователя.'''
    template = 'blog/profile.html'
    user = get_object_or_404(User, username=name)
    profile_posts = user.posts.all()
    page_number = request.GET.get('page')
    page_obj = get_paginated_posts(profile_posts, page_number)
    context = {
        'profile': user,
        'page_obj': page_obj,
    }
    return render(request, template, context)


class PostListView(ListView):
    template_name = 'blog/index.html'
    model = Post
    ordering = '-pub_date'
    paginate_by = settings.POSTS_PAGE

    def get_queryset(self):
        return Post.objects.filter(
            is_published=True,
            pub_date__lte=timezone.now(),
            category__is_published=True,
        ).select_related('author', 'category', 'location')


def category_posts(request, category_slug):
    '''Отображение по категории постов'''
    templates = 'blog/category.html'
    current_time = timezone.now()
    category = get_object_or_404(
        Category,
        is_published=True,
        slug=category_slug
    )
    post_list = category.posts.filter(
        pub_date__lte=current_time,
        is_published=True,
    ).select_related('category')
    paginator = Paginator(post_list, settings.POSTS_PAGE)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    posts = page_obj.object_list
    context = {
        'category': category,
        'posts': posts,
        'page_obj': page_obj
    }
    return render(request, templates, context)


class PostCreateView(LoginRequiredMixin, CreateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def form_valid(self, form):
        '''Проверка валидности формы.'''
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        '''Получение адреса.'''
        url = reverse(
            'blog:profile',
            args=(self.request.user.get_username(),)
        )
        return url


class DispatchMixin:
    def dispatch(self, request, *args, **kwargs):
        '''Отправляет изменения/удаления поста'''
        self.post_id = kwargs['pk']
        if self.get_object().author != request.user:
            return redirect('blog:post_detail', pk=self.post_id)
        return super().dispatch(request, *args, **kwargs)


class PostUpdateView(LoginRequiredMixin, DispatchMixin, UpdateView):
    model = Post
    form_class = PostForm
    template_name = 'blog/create.html'

    def get_success_url(self):
        '''Получение адреса.'''
        url = reverse('blog:post_detail', args=(self.post_id,))
        return url


class PostDeleteView(LoginRequiredMixin, DispatchMixin, DeleteView):
    model = Post
    success_url = reverse_lazy('blog:index')
    template_name = 'blog/create.html'


class PostDetailView(DetailView):
    model = Post
    template_name = 'blog/detail.html'

    def get_object(self):
        queryset = Post.objects.filter(
            Q(is_published=True) | Q(author=self.request.user)
        )
        return get_object_or_404(
            queryset,
            pk=self.kwargs.get('pk'),
        )

    def get_context_data(self, **kwargs):
        '''Получение данных контекста'''
        context = super().get_context_data(**kwargs)
        context['form'] = CommentForm()
        context['comments'] = (
            self.object.comments.select_related(
                'author'
            )
        )
        return context


@login_required
def add_comment(request, pk):
    '''Добавление комментария'''
    post = get_object_or_404(Post, pk=pk)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('blog:post_detail', pk=pk)


@login_required
def edit_comment(request, comment_id, post_id):
    '''Изменение комментария'''
    instance = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    form = CommentForm(request.POST or None, instance=instance)
    if instance.author != request.user:
        return redirect('blog:post_detail', pk=post_id)
    context = {
        'form': form,
        'comment': instance
    }

    if form.is_valid():
        form.save()
        return redirect('blog:post_detail', pk=post_id)
    return render(request, 'blog/comment.html', context)


@login_required
def delete_comment(request, comment_id, post_id):
    '''Удаление комментария'''
    instance = get_object_or_404(Comment, id=comment_id, post_id=post_id)
    if instance.author != request.user:
        return redirect('blog:post_detail', pk=post_id)
    context = {'comment': instance}
    if request.method == 'POST':
        instance.delete()
        return redirect('blog:post_detail', pk=post_id)
    return render(request, 'blog/comment.html', context)
