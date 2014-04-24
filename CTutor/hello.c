#include <stdio.h>
#include <stdlib.h>
int g = 42;
float u = 5;

struct node {
  int field;
  struct node* next;
};

// Modify global var
void f() {
    g = g + 1;
    printf("Hello world1!\n");
    printf("Hello world2!\n");
}

int bar_2(int temp2) {
   int temp = temp2*2;
   return temp;
}

// Check parameter passing and return value
int bar(int tmp) {
    tmp = tmp + 2;
    tmp = bar_2(tmp);
    printf("Tmp:%d\n", tmp); 
    return tmp;
}

int
main(int argc, char *argv[])
{
//  struct node nd;
//  int a[10];
  int x;
  int y=10;
  x  = y+1;
  struct node* root = (struct node*)malloc(sizeof(struct node));
  root->field = 3;
  root->next = (struct node*)malloc(sizeof(struct node));
  root->next->field = 2;
  free(root->next);
//  root->next = 0;
  free(root);
//  root = 0;

  int i = 0;
  i = i + 1;
  f();

  int b = bar(i);
  printf("b=%d\n", b);

  return 0;
}
