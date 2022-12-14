from django.shortcuts import get_object_or_404, render, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView

# Login->로그인했을 때만 페이지가 정상적으로 보이게 / User-> 페이지에 접근가능한 사용자를 최고관리자 or 스태프로 제한
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Post, Category, Tag, Comment
from .forms import CommentForm

# 포스트 작성자만 수정할 수 있게 구현
from django.core.exceptions import PermissionDenied

# 태그가 없으면 새로 만들도록
from django.utils.text import slugify

# 검색기능
from django.db.models import Q

# 요청을 받으면 포스트에 받은객체를 rendering해서 넣어줌
class PostList(ListView):
    model = Post
    ordering = '-pk'
    paginate_by = 5 # 1페이지에 5개의 포스트만 보여주기

    # category 추가 (get_context_data 내장 함수 오버라이딩)
    def get_context_data(self, **kwargs):
        context = super(PostList, self).get_context_data()
        context['categories'] = Category.objects.all()
        context['no_category_post_count'] = Post.objects.filter(category=None).count()
        context['comment_form'] = CommentForm

        return context

# 장고에서 제공하는 CreateView를 상속  
class PostCreate(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Post
    fields = ['title', 'hook_text', 'content', 'head_image', 'file_upload', 'category']

    # 접근가능한 사용자를 최고관리자 or 스태프
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    # 자동으로 author 필드 채우기(form_valid => 방문자가 폼에 담아 보낸 유효한 정보를 사용해 포스트를 만들고, 이 포스트의 고유 경로로 보내주는 역할)
    def form_valid(self, form):
        current_user = self.request.user
        if current_user.is_authenticated and (current_user.is_staff or current_user.is_superuser):
            form.instance.author = current_user

            # 태그 출력
            response = super(PostCreate, self).form_valid(form)
            tags_str = self.request.POST.get('tags_str')
            if tags_str:
                tags_str = tags_str.strip()
                tags_str = tags_str.replace(',', ';')
                tags_list = tags_str.split(';')

                for t in tags_list:
                    t = t.strip()
                    tag, is_tag_created = Tag.objects.get_or_create(name=t)
                    if is_tag_created:
                        # slugify=> 태그이름 검색시 slug 자동생성
                        tag.slug = slugify(t, allow_unicode=True)
                        tag.save()
                    self.object.tags.add(tag)
            return response
            # return super(PostCreate, self).form_valid(form)
        else:
            return redirect('/blog/')

# 장고에서 제공하는 PostUpdate 클래스를 상속(CBV스타일)
class PostUpdate(LoginRequiredMixin, UpdateView):
    model = Post
    fields = ['title', 'hook_text', 'content', 'head_image', 'file_upload', 'category', 'tags']

    # 템플릿 파일 지정
    template_name = 'blog/post_update_form.html'

    # tag가 존재하면 해당 tag 이름을 리스트형태로 담은 후 하나의 문자열로 생성(get_context_data이용) 후 딕셔너리 형태로 저장
    def get_context_data(self, **kwargs):
        context = super(PostUpdate, self).get_context_data()
        if self.object.tags.exists():
            tags_str_list = list()
            for t in self.object.tags.all():
                tags_str_list.append(t.name)
            context['tags_str_default'] = ';'.join(tags_str_list)
        return context

    # dispatch => 방문자가 웹 사이트서버에 Get방식으로 요청했는지 Post 방식으로 요철했는지 판단
    # 권한이 없는 사용자가 postupdate를 사용하려고 하면 통신방식에 상관없이 접근 할 수 없도록 수정
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user == self.get_object().author:
            return super(PostUpdate, self).dispatch(request, *args, **kwargs)
        else:
            raise PermissionDenied
            # 권한이 없는 사용자가 포스트를 수정하려 할 때 오류 메세지 출력

    # 태그 삭제 기능 추가
    def form_valid(self, form):
        response = super(PostUpdate, self).form_valid(form)
        self.object.tags.clear()

        tags_str = self.request.POST.get('tags_str')
        if tags_str:
            tags_str = tags_str.strip()
            tags_str = tags_str.replace(',', ';')
            tags_list = tags_str.split(';')

            for t in tags_list:
                t = t.strip()
                tag, is_tag_created = Tag.objects.get_or_create(name=t)
                if is_tag_created:
                    # slugify=> 태그이름 검색시 slug 자동생성
                    tag.slug = slugify(t, allow_unicode=True)
                    tag.save()
                self.object.tags.add(tag)
        return response
        # return super(PostCreate, self).form_valid(form)

# 카테고리 페이지(해당 카테고리 포스트만 보여주도록)
def category_page(request, slug):

    # 카테고리 미분류일 때
    if slug == 'no_category':
        category = '미분류'
        post_list = Post.objects.filter(category=None)
    else:
        # 동일한 slug를 갖는 카테고리를 불러옴(category변수에 저장)
        category = Category.objects.get(slug=slug)
        post_list = Post.objects.filter(category=category)

    return render(
        request,
            # post_list와 동일한 출력모양(템플릿 설정)
        'blog/post_list.html',
        {
            # post_list에 context 부분 정의
            'post_list': post_list,
            'categories':Category.objects.all(),
            'no_category_post_count':Post.objects.filter(category=None).count(),
            'category':category,
        }
    )

# tag 페이지(해당 tag만 보여주도록)
def tag_page(request, slug):
    tag = Tag.objects.get(slug=slug)
    post_list = tag.post_set.all()


    return render(
        request,
            # post_list와 동일한 출력모양(템플릿 설정)
        'blog/post_list.html',
        {
            'post_list': post_list,
            'tag' : tag,
            'categories':Category.objects.all(),
            'no_category_post_count':Post.objects.filter(category=None).count(),
        }
    )

class PostDetail(DetailView):
    model = Post

    # category 추가 (get_context_data 내장 함수 오버라이딩)
    def get_context_data(self, **kwargs):
        context = super(PostDetail, self).get_context_data()
        context['categories'] = Category.objects.all()
        context['no_category_post_count'] = Post.objects.filter(category=None).count()
        context['comment_form'] = CommentForm

        return context

# new_comment
def new_comment(request, pk):
    if request.user.is_authenticated:
        post = get_object_or_404(Post, pk=pk)

        if request.method == 'POST':
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.post = post
                comment.author = request.user
                comment.save()
                return redirect(comment.get_absolute_url())
        else:
            return redirect(post.get_absolute_url())
    else:
        raise PermissionDenied

# 댓글 수정 class(로그인이 )
class CommentUpdate(LoginRequiredMixin, UpdateView):
    model = Comment
    form_class = CommentForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user == self.get_object().author:
            return super(CommentUpdate, self).dispatch(request, *args, **kwargs)
        else:
            raise PermissionDenied

# delete_comment 함수 생성 (방문자의 권한 확인 => 조건 만족시 해당 댓글 삭제 가능 없다면 PermissionDenied 오류발생)
def delete_comment(request, pk):
    # pk에 해당 댓글이 없으면 404 오류 발생
    comment = get_object_or_404(Comment, pk=pk)
    post = comment.post
    if request.user.is_authenticated and request.user == comment.author:
        comment.delete()
        return redirect(post.get_absolute_url())
    else:
        raise PermissionDenied

# 검색기능 구현 (PostList클래스 상속)
class PostSearch(PostList):
    # 검색 시 한 페이지에 출력
    paginate_by = None
    
    #get_queryset을 오버라이딩(url을 통해 넘어온 검색어를 q라는 변수에 저장)
    #Q => 여러쿼리를 동시에 쓸 때 사용 (title과 tags에 q가 포함되어있는 레코드를 db에서 가져옴 * __ 쿼리 조건<.과 같은 의미>)
    #distinct => 중복 방지
    def get_queryset(self):
        q = self.kwargs['q']
        post_list = Post.objects.filter(
            Q(title__contains=q) | Q(tags__name__contains=q)
        ).distinct()
        return post_list

    # 해당 q가 몇개의 포스트가 포함되어있는지 출력
    def get_context_data(self, **kwargs):
        context = super(PostSearch, self).get_context_data()
        q = self.kwargs['q']
        context['search_info'] = f'검색어: {q} ({self.get_queryset().count()})'

        return context

# Create your views here.

# #FBV 방법
# def index(request):
#     posts = Post.objects.all().order_by('-pk')
#     # post에 있는 객체를 모두 가져옴 ('-pk'는 역순)

#     return render(
#         request, 
#         'blog/index.html',
#         {
#             'posts' : posts,
#         }
#     )
# 
#single_post_page 함수 정의
# def single_post_page(request, pk):
#     post = Post.objects.get(pk=pk)

#     return render(
#         request,
#         'blog/single_post_page.html',
#         {
#             'post':post,
#         }
#     )
