#include "ds4_q1_ref.h"

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

static int parse_i64(const char *s, int64_t *out) {
    char *end = NULL;
    errno = 0;
    long long v = strtoll(s, &end, 10);
    if (errno || !end || *end != '\0') return -1;
    *out = (int64_t)v;
    return 0;
}

static int parse_type(const char *s) {
    if (strcmp(s, "iq2_xxs") == 0 || strcmp(s, "16") == 0) return DS4_Q1_REF_TYPE_IQ2_XXS;
    if (strcmp(s, "q2_k") == 0 || strcmp(s, "10") == 0) return DS4_Q1_REF_TYPE_Q2_K;
    return -1;
}

static int read_all(uint8_t *dst, size_t n) {
    size_t off = 0;
    while (off < n) {
        const size_t got = fread(dst + off, 1, n - off, stdin);
        if (got == 0) return ferror(stdin) ? -1 : -2;
        off += got;
    }
    return 0;
}

int main(int argc, char **argv) {
#ifdef _WIN32
    _setmode(_fileno(stdin), _O_BINARY);
    _setmode(_fileno(stdout), _O_BINARY);
#endif
    if (argc != 5 || strcmp(argv[1], "convert") != 0) {
        fprintf(stderr, "usage: %s convert <iq2_xxs|q2_k|16|10> <nrows> <ncols>\n", argv[0]);
        return 2;
    }
    const int type_id = parse_type(argv[2]);
    int64_t nrows = 0;
    int64_t ncols = 0;
    if (type_id < 0 || parse_i64(argv[3], &nrows) || parse_i64(argv[4], &ncols) || nrows <= 0 || ncols <= 0) {
        fprintf(stderr, "invalid arguments\n");
        return 2;
    }
    const size_t src_row = ds4_q1_ref_row_size(type_id, ncols);
    const size_t dst_row = ds4_q1_ref_row_size(DS4_Q1_REF_TYPE_Q1_0, ncols);
    if (!src_row || !dst_row) {
        fprintf(stderr, "unsupported row geometry\n");
        return 2;
    }
    const size_t src_size = src_row * (size_t)nrows;
    const size_t dst_size = dst_row * (size_t)nrows;
    uint8_t *src = (uint8_t *)malloc(src_size);
    uint8_t *dst = (uint8_t *)malloc(dst_size);
    if (!src || !dst) {
        fprintf(stderr, "allocation failed\n");
        free(src);
        free(dst);
        return 3;
    }
    if (read_all(src, src_size) != 0) {
        fprintf(stderr, "stdin payload too short\n");
        free(src);
        free(dst);
        return 4;
    }
    const int rc = ds4_q1_ref_convert_rows_to_q1_0(type_id, src, src_size, nrows, ncols, dst, dst_size);
    if (rc != 0) {
        fprintf(stderr, "conversion failed: %d\n", rc);
        free(src);
        free(dst);
        return 5;
    }
    if (fwrite(dst, 1, dst_size, stdout) != dst_size) {
        fprintf(stderr, "stdout write failed\n");
        free(src);
        free(dst);
        return 6;
    }
    free(src);
    free(dst);
    return 0;
}
